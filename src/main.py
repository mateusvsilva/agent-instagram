import asyncio
import random
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import get_settings
from .domain.ports import (
    BriefingRepository,
    ImageGenerator,
    Publisher,
)
from .handlers.approval_handler import ApprovalHandler
from .handlers.command_handler import CommandHandler
from .handlers.conversation_handler import ConversationHandler
from .domain.models.brand import BrandIdentity
from .domain.models.content import ContentRequest, MarketResearch, SubjectOrigin
from .domain.models.enums import ApprovalStatus, PostStatus
from .domain.models.post import ComposedPost, Post
from .domain.models.schedule import Schedule
from .domain.models.template import PromptTemplate
from .handlers.creation_handler import CreationHandler
from .services.art_director import ArtDirectorService
from .services.brain_client import build_brain_client
from .services.briefing_repository import build_briefing_repository
from .services.buffer_publisher import BufferPublisherService
from .services.caption_generator import CaptionGeneratorService
from .services.creation_service import CreationService
from .services.image_generator import ImageGeneratorService
from .services.market_research import MarketResearchError, build_market_research_service
from .services.post_composer import PostComposerService
from .services.prompts_loader import PromptsLoaderService
from .services.scheduler import SchedulerService
from .services.storage import StorageService
from .services.telegram_bot import TelegramBotService
from .utils.cost_tracker import BudgetTracker
from .utils.logger import get_logger, setup_logger

settings = get_settings()
setup_logger("src", level=settings.log_level, log_file=Path("./data/agent.log"))
logger = get_logger(__name__)


class InstagramAgent:
    def __init__(self):
        self._budget = BudgetTracker(
            daily_limit=settings.daily_budget_usd,
            monthly_limit=settings.monthly_budget_usd,
            alert_threshold=settings.budget_alert_threshold,
        )
        self._storage = StorageService(db_path=settings.db_path)
        self._image_generator: ImageGenerator = self._build_image_generator(settings)

        # "Cérebro" (Claude) compartilhado por pesquisa e legenda.
        self._brain = build_brain_client(settings)
        self._caption_generator = CaptionGeneratorService(brain=self._brain)
        self._post_composer = PostComposerService(
            settings=settings, caption_generator=self._caption_generator
        )
        self._research = build_market_research_service(self._brain)
        self._prompts_loader = PromptsLoaderService(settings=settings)
        self._briefing_repo: BriefingRepository = build_briefing_repository(settings)
        # Identidade de marca carregada na inicialização (HU-BACKEND-05).
        self._brand: BrandIdentity = BrandIdentity()

        self._publisher: Publisher = self._build_publisher(settings)
        self._approval_handler = ApprovalHandler(allowed_chat_ids=[settings.telegram_chat_id])
        self._telegram = TelegramBotService(settings=settings, approval_handler=self._approval_handler)
        self._scheduler = SchedulerService(settings=settings, job_callback=self._handle_scheduled_job)
        # Criação conversacional (/criar): art_director e creation_service são
        # construídos em start(), após o load da marca, para capturarem a marca
        # já carregada (self._brand muda de BrandIdentity() para o conteúdo real).
        self._art_director: Optional[ArtDirectorService] = None
        self._creation_service: Optional[CreationService] = None
        self._creation_handler: Optional[CreationHandler] = None
        self._conversation_handler: Optional[ConversationHandler] = None
        self._command_handler: Optional[CommandHandler] = None
        self._shutdown_event = asyncio.Event()

    def _build_image_generator(self, settings):
        provider = (settings.image_provider or "gemini").lower()
        if provider == "openai":
            logger.info("Image provider: OpenAI (DALL-E)")
            return ImageGeneratorService(settings=settings, budget_tracker=self._budget)
        logger.info("Image provider: Gemini (Google)")
        from .services.gemini_image_generator import GeminiImageGeneratorService
        return GeminiImageGeneratorService(settings=settings, budget_tracker=self._budget)

    @staticmethod
    def _build_publisher(settings):
        logger.info("Publisher backend: Buffer (API oficial)")
        from .services.image_host import build_image_uploader
        return BufferPublisherService(settings=settings, image_uploader=build_image_uploader(settings))

    async def start(self) -> None:
        logger.info("Starting Instagram Agent...")

        await self._storage.initialize()

        # Carrega a identidade de marca da pasta prompts/ (HU-BACKEND-05).
        self._brand = self._prompts_loader.load()

        # Criação conversacional (/criar): construída aqui para capturar a marca
        # já carregada acima (em __init__ a marca ainda é o placeholder vazio).
        self._art_director = ArtDirectorService(brain=self._brain, brand=self._brand)
        self._creation_service = CreationService(
            brain=self._brain,
            art_director=self._art_director,
            image_generator=self._image_generator,
            brand=self._brand,
            budget=self._budget,
            post_composer=self._post_composer,
            telegram=self._telegram,
            settings=settings,
        )
        self._creation_service.on_complete = self._publish_composed
        self._creation_handler = CreationHandler(
            allowed_chat_ids=[settings.telegram_chat_id],
            creation_service=self._creation_service,
        )
        self._conversation_handler = ConversationHandler(
            allowed_chat_ids=[settings.telegram_chat_id],
            subject_callback=self._subject_generate,
            creation_service=self._creation_service,
        )

        await self._telegram.start()

        self._command_handler = CommandHandler(
            allowed_chat_ids=[settings.telegram_chat_id],
            storage=self._storage,
            scheduler=self._scheduler,
            force_callback=self._force_generate,
            criar_callback=self._creation_service.start,
        )
        self._telegram.register_commands(
            cmd_start=self._command_handler.cmd_start,
            cmd_status=self._command_handler.cmd_status,
            cmd_history=self._command_handler.cmd_history,
            cmd_schedule=self._command_handler.cmd_schedule,
            cmd_pause=self._command_handler.cmd_pause,
            cmd_resume=self._command_handler.cmd_resume,
            cmd_force=self._command_handler.cmd_force,
            cmd_metrics=self._command_handler.cmd_metrics,
            on_message=self._conversation_handler.handle_message,
            cmd_criar=self._command_handler.cmd_criar,
            cmd_comandos=self._command_handler.cmd_comandos,
            creation_handler=self._creation_handler,
        )

        last_published = await self._storage.get_last_published_at()
        if last_published:
            self._publisher.set_last_post_at(last_published)

        await self._scheduler.start()

        schedules_file = Path("./data/schedules.json")
        if schedules_file.exists():
            self._scheduler.load_schedules_from_file(schedules_file)

        logger.info("Instagram Agent fully started.")

        await self._shutdown_event.wait()

    async def stop(self) -> None:
        logger.info("Shutting down Instagram Agent...")
        await self._scheduler.stop()
        await self._telegram.stop()
        logger.info("Instagram Agent stopped.")

    async def _handle_scheduled_job(self, schedule: Schedule, template: Optional[PromptTemplate]) -> None:
        if template is None:
            logger.error("No template available for schedule %s", schedule.id)
            return
        # HU-BACKEND-06: briefing semanal direciona o assunto; sem briefing, cai
        # para o sorteio de template (assunto = nome do template).
        request = await self._resolve_subject(template)
        # RN-BACKEND-04: tentativas de "redo" do pipeline vêm de MAX_REDO_ATTEMPTS
        # (consistente com _force_generate e _subject_generate). Não confundir com
        # Schedule.max_retries, que é o retry de infraestrutura do job (APScheduler).
        await self._run_pipeline(
            template=template,
            request=request,
            schedule_id=schedule.id,
            max_attempts=settings.max_redo_attempts,
        )

    async def _force_generate(self) -> None:
        """`/force` legado: sorteia template e gera (HU-BACKEND-01 não remove isso)."""
        template = self._pick_template()
        if template is None:
            await self._telegram.notify("❌ Nenhum template disponível para geração forçada.")
            return
        request = await self._resolve_subject(template)
        await self._run_pipeline(
            template=template,
            request=request,
            schedule_id=None,
            max_attempts=settings.max_redo_attempts,
        )

    async def _subject_generate(self, subject: str) -> None:
        """HU-BACKEND-01: pedido de assunto livre via Telegram ("poste sobre X")."""
        template = self._pick_template()
        if template is None:
            await self._telegram.notify("❌ Nenhum template disponível para gerar o post.")
            return
        request = ContentRequest(subject=subject, origin=SubjectOrigin.TELEGRAM)
        await self._run_pipeline(
            template=template,
            request=request,
            schedule_id=None,
            max_attempts=settings.max_redo_attempts,
        )

    async def _resolve_subject(self, template: PromptTemplate) -> ContentRequest:
        """Decide o assunto de um post programado: briefing > sorteio (HU-BACKEND-06)."""
        briefing = await self._briefing_repo.get_active(settings.agent_id)
        if briefing is not None:
            return ContentRequest(
                subject=briefing.subject,
                origin=SubjectOrigin.BRIEFING,
                notes=briefing.notes,
            )
        return ContentRequest(subject=template.name, origin=SubjectOrigin.TEMPLATE)

    def _pick_template(self) -> Optional[PromptTemplate]:
        templates = self._scheduler.get_templates()
        if not templates:
            return None
        return random.choice(templates)

    async def _run_pipeline(
        self,
        template: PromptTemplate,
        request: ContentRequest,
        schedule_id: Optional[str],
        max_attempts: int,
    ) -> None:
        post_id = str(uuid.uuid4())
        post = Post(
            id=post_id,
            template_id=template.id,
            schedule_id=schedule_id,
            max_attempts=max_attempts,
        )
        await self._storage.save_post(post)
        logger.info(
            "Pipeline iniciado: post=%s assunto='%s' origem=%s",
            post_id, request.subject, request.origin.value,
        )

        # HU-BACKEND-02: pesquisa ANTES de imagem e legenda. Se falhar, registra
        # o erro e NÃO segue silenciosamente.
        try:
            research = await self._research.run(request)
        except MarketResearchError as exc:
            logger.error("Pesquisa de mercado falhou para post %s: %s", post_id, exc)
            await self._storage.save_error(post_id, f"market_research: {exc}")
            await self._storage.update_status(post_id, status=PostStatus.FAILED, approval_status=None)
            await self._telegram.notify(
                f"❌ Pesquisa de mercado falhou para `{post_id[:8]}`:\n`{exc}`"
            )
            return

        # Instrução de ajuste acumulada via redo conversacional (HU-BACKEND-04).
        instruction = ""

        for attempt in range(1, max_attempts + 1):
            post.attempt = attempt
            logger.info("Pipeline attempt %d/%d for post %s", attempt, max_attempts, post_id)

            try:
                composed = await self._generate_and_compose(
                    post, template, request=request, research=research, instruction=instruction
                )
            except Exception as exc:
                logger.error("Generation failed for post %s: %s", post_id, exc)
                await self._storage.save_error(post_id, str(exc))
                await self._storage.update_status(
                    post_id, status=PostStatus.FAILED, approval_status=None
                )
                await self._telegram.notify(f"❌ Falha ao gerar post `{post_id[:8]}`:\n`{exc}`")
                return

            post.status = PostStatus.AWAITING_APPROVAL
            post.composed_image_paths = composed.composed_image_paths
            post.caption = composed.caption
            post.hashtags = composed.hashtags
            post.total_cost_usd = composed.total_cost_usd
            post.images = composed.images
            await self._storage.save_post(post)

            try:
                message_id = await self._telegram.send_preview(composed)
                post.telegram_message_id = message_id
                await self._storage.update_status(post_id, telegram_message_id=message_id)
            except Exception as exc:
                logger.error("Failed to send Telegram preview: %s", exc)
                await self._storage.save_error(post_id, str(exc))
                return

            approval = await self._telegram.await_approval(post_id)
            post.approval_status = approval

            if approval == ApprovalStatus.APPROVED:
                await self._publish(post)
                return

            if approval == ApprovalStatus.REJECTED:
                await self._storage.update_status(
                    post_id,
                    status=PostStatus.DISCARDED,
                    approval_status=ApprovalStatus.REJECTED,
                )
                logger.info("Post %s rejected by user", post_id)
                return

            if approval == ApprovalStatus.EXPIRED:
                await self._storage.update_status(
                    post_id,
                    approval_status=ApprovalStatus.EXPIRED,
                    status=PostStatus.DISCARDED,
                )
                logger.info("Post %s expired without approval", post_id)
                return

            if approval == ApprovalStatus.REDO:
                # RN-BACKEND-04: respeita MAX_REDO_ATTEMPTS — não relaxa o limite.
                if attempt >= max_attempts:
                    await self._telegram.notify(
                        f"⚠️ Post `{post_id[:8]}` atingiu o máximo de {max_attempts} tentativas."
                    )
                    await self._storage.update_status(
                        post_id, status=PostStatus.DISCARDED, approval_status=ApprovalStatus.REDO
                    )
                    return
                # HU-BACKEND-04: PERGUNTA o que mudar antes de regenerar (loop).
                instruction = await self._ask_redo_instruction(post_id)
                await self._telegram.notify(
                    f"🔄 Regenerando post (tentativa {attempt + 1}/{max_attempts})..."
                )
                continue

        logger.warning("Post %s exhausted all attempts", post_id)

    async def _ask_redo_instruction(self, post_id: str) -> str:
        """Pergunta ao operador o que alterar e aguarda a resposta (HU-BACKEND-04).

        Se o operador não responder dentro do timeout de aprovação, segue sem
        instrução específica (regenera de forma genérica), preservando o fluxo.
        """
        future = self._conversation_handler.register_answer(post_id)
        question_message_id = await self._telegram.notify(
            f"✍️ O que você quer que eu altere no post `{post_id[:8]}`? "
            "(responda *a esta mensagem*)"
        )
        # Vincula a pergunta ao post para rotear a resposta certa quando houver
        # mais de um post aguardando ajuste em paralelo (HU-BACKEND-04).
        self._conversation_handler.link_question(post_id, question_message_id)
        try:
            answer = await asyncio.wait_for(future, timeout=float(settings.telegram_approval_timeout))
            logger.info("Instrução de redo para post %s: %.80s", post_id, answer)
            return answer
        except asyncio.TimeoutError:
            self._conversation_handler.cancel_answer(post_id)
            logger.info("Sem resposta de redo para post %s — regenerando sem instrução.", post_id)
            return ""

    async def _generate_and_compose(
        self,
        post: Post,
        template: PromptTemplate,
        *,
        request: ContentRequest,
        research: MarketResearch,
        instruction: str = "",
    ) -> ComposedPost:
        await self._storage.update_status(post.id, status=PostStatus.GENERATING)
        images = await self._image_generator.generate(
            template=template,
            post_id=post.id,
            count=template.image_count,
            image_brief=self._brand.image_brief(),
            subject=request.subject,
        )

        await self._storage.update_status(post.id, status=PostStatus.COMPOSING)
        composed = await self._post_composer.compose(
            images=images,
            template=template,
            post_id=post.id,
            brand=self._brand,
            research=research,
            subject=request.subject,
            instruction=instruction,
        )
        return composed

    async def _publish_composed(self, composed: ComposedPost) -> None:
        """Publica um post vindo da criação conversacional. O botão 'Aprovar e
        publicar' já fez o papel da aprovação — aqui só persiste e publica."""
        post = Post(**composed.model_dump())
        post.status = PostStatus.AWAITING_APPROVAL
        await self._storage.save_post(post)
        await self._publish(post)

    async def _publish(self, post: Post) -> None:
        post.approval_status = ApprovalStatus.APPROVED
        post.approved_at = datetime.now(timezone.utc)
        post.status = PostStatus.PUBLISHING
        await self._storage.update_status(
            post.id,
            status=PostStatus.PUBLISHING,
            approval_status=ApprovalStatus.APPROVED,
            approved_at=post.approved_at,
        )

        composed = ComposedPost(**post.model_dump())
        result = await self._publisher.publish_carousel(composed)

        if result.success:
            post.status = PostStatus.PUBLISHED
            post.instagram_media_id = result.media_id
            post.published_at = datetime.now(timezone.utc)
            await self._storage.update_status(
                post.id,
                status=PostStatus.PUBLISHED,
                approval_status=ApprovalStatus.PUBLISHED,
                instagram_media_id=result.media_id,
                published_at=post.published_at,
            )
            await self._telegram.notify(
                f"✅ Post `{post.id[:8]}` publicado com sucesso!\nMedia ID: `{result.media_id}`"
            )
            logger.info("Post %s published, media_id=%s", post.id, result.media_id)
        else:
            post.status = PostStatus.FAILED
            post.error = result.error
            await self._storage.update_status(
                post.id, status=PostStatus.FAILED, error=result.error
            )
            await self._telegram.notify(
                f"❌ Falha ao publicar post `{post.id[:8]}`:\n`{result.error}`"
            )
            logger.error("Post %s publish failed: %s", post.id, result.error)


def _setup_signal_handlers(agent: InstagramAgent, loop: asyncio.AbstractEventLoop) -> None:
    def _shutdown():
        logger.info("Signal received, shutting down...")
        loop.create_task(agent.stop())
        agent._shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except (NotImplementedError, ValueError):
            signal.signal(sig, lambda s, f: _shutdown())


async def _main() -> None:
    agent = InstagramAgent()
    loop = asyncio.get_running_loop()
    _setup_signal_handlers(agent, loop)
    try:
        await agent.start()
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(_main())
