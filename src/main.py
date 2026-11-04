import asyncio
import random
import signal
import uuid
from datetime import datetime, timezone
from typing import Coroutine, Optional

from .config import Settings, get_settings
from .domain.models.content import ContentRequest, MarketResearch, SubjectOrigin
from .domain.models.enums import ApprovalStatus, PostStatus
from .domain.models.post import ComposedPost, Post
from .domain.models.schedule import Schedule
from .domain.models.template import PromptTemplate
from .domain.ports import ImageGenerator
from .handlers.approval_handler import ApprovalHandler
from .handlers.command_handler import CommandHandler
from .handlers.conversation_handler import ConversationHandler
from .handlers.creation_handler import CreationHandler
from .services.art_director import ArtDirectorService
from .services.brain_client import build_brain_client
from .services.briefing_repository import FileBriefingRepository
from .services.buffer_publisher import BufferPublisherService
from .services.caption_generator import CaptionGeneratorService
from .services.creation_service import CreationService
from .services.image_host import build_image_uploader
from .services.market_research import MarketResearchError, MarketResearchService
from .services.post_composer import PostComposerService
from .services.prompts_loader import PromptsLoaderService
from .services.scheduler import SchedulerService
from .services.storage import StorageService
from .services.telegram_bot import TelegramBotService
from .utils.cost_tracker import BudgetTracker
from .utils.logger import get_logger, setup_logger

logger = get_logger(__name__)


def build_image_generator(settings: Settings, budget: BudgetTracker) -> ImageGenerator:
    logger.info("Image provider: %s", settings.image_provider)
    if settings.image_provider == "openai":
        from .services.image_generator import ImageGeneratorService

        return ImageGeneratorService(settings=settings, budget_tracker=budget)
    from .services.gemini_image_generator import GeminiImageGeneratorService

    return GeminiImageGeneratorService(settings=settings, budget_tracker=budget)


class InstagramAgent:
    def __init__(self, settings: Settings):
        self._settings = settings
        chat_ids = [settings.telegram_chat_id]

        self._budget = BudgetTracker(
            daily_limit=settings.daily_budget_usd,
            monthly_limit=settings.monthly_budget_usd,
            alert_threshold=settings.budget_alert_threshold,
        )
        self._storage = StorageService(db_path=settings.db_path)
        self._brain = build_brain_client(settings)
        self._brand = PromptsLoaderService(settings).load()
        self._image_generator = build_image_generator(settings, self._budget)
        self._post_composer = PostComposerService(settings, CaptionGeneratorService(self._brain))
        self._research = MarketResearchService(self._brain)
        self._briefing_repo = FileBriefingRepository(settings.briefing_file)
        self._publisher = BufferPublisherService(settings, build_image_uploader(settings))

        self._approval_handler = ApprovalHandler(chat_ids)
        self._telegram = TelegramBotService(settings, self._approval_handler)
        self._scheduler = SchedulerService(settings, self._handle_scheduled_job)
        self._creation_service = CreationService(
            brain=self._brain,
            art_director=ArtDirectorService(brain=self._brain, brand=self._brand),
            image_generator=self._image_generator,
            brand=self._brand,
            budget=self._budget,
            post_composer=self._post_composer,
            telegram=self._telegram,
            settings=settings,
            on_complete=self._publish_composed,
        )
        self._creation_handler = CreationHandler(chat_ids, self._creation_service)
        self._conversation_handler = ConversationHandler(chat_ids, self._creation_service)
        self._command_handler = CommandHandler(
            chat_ids, self._storage, self._scheduler, self._start_force, self._creation_service.start,
            self._start_subject,
        )

        self._tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    def request_stop(self) -> None:
        self._shutdown_event.set()

    async def run(self) -> None:
        logger.info("Starting Instagram Agent...")
        await self._storage.initialize()
        expired = await self._storage.expire_pending()
        if expired:
            logger.info("%d post(s) pendentes de execução anterior marcados como expirados.", expired)
        await self._restore_budget()

        last_published = await self._storage.get_last_published_at()
        if last_published:
            self._publisher.set_last_post_at(last_published)

        await self._telegram.start()
        self._telegram.register_handlers(
            commands=self._command_handler.commands(),
            on_message=self._conversation_handler.handle_message,
            on_creation_callback=self._creation_handler.handle_callback,
        )

        self._scheduler.start()
        if self._settings.schedules_file.exists():
            self._scheduler.load_schedules_from_file(self._settings.schedules_file)

        await self._telegram.notify("🤖 *Instagram Agent iniciado.* Pronto para operar.")
        logger.info("Instagram Agent fully started.")
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        logger.info("Shutting down Instagram Agent...")
        self._scheduler.stop()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._telegram.stop()
        logger.info("Instagram Agent stopped.")

    async def _restore_budget(self) -> None:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        self._budget.restore(
            daily_spent=await self._storage.get_cost_since(day_start),
            monthly_spent=await self._storage.get_cost_since(day_start.replace(day=1)),
        )
        logger.info("Orçamento restaurado do banco: %s", self._budget.summary())

    def _spawn(self, coro: Coroutine) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("Pipeline em background falhou", exc_info=task.exception())

    async def _start_force(self) -> None:
        self._spawn(self._force_generate())

    async def _start_subject(self, subject: str) -> None:
        self._spawn(self._subject_generate(subject))

    async def _handle_scheduled_job(self, schedule: Schedule, template: Optional[PromptTemplate]) -> None:
        if template is None:
            logger.error("No template available for schedule %s", schedule.id)
            return
        await self._run_pipeline(template, await self._resolve_subject(template), schedule_id=schedule.id)

    async def _force_generate(self) -> None:
        template = self._pick_template()
        if template is None:
            await self._telegram.notify("❌ Nenhum template disponível para geração forçada.")
            return
        await self._run_pipeline(template, await self._resolve_subject(template))

    async def _subject_generate(self, subject: str) -> None:
        template = self._pick_template()
        if template is None:
            await self._telegram.notify("❌ Nenhum template disponível para gerar o post.")
            return
        await self._run_pipeline(template, ContentRequest(subject=subject, origin=SubjectOrigin.TELEGRAM))

    async def _resolve_subject(self, template: PromptTemplate) -> ContentRequest:
        briefing = await self._briefing_repo.get_active(self._settings.agent_id)
        if briefing is not None:
            return ContentRequest(subject=briefing.subject, origin=SubjectOrigin.BRIEFING, notes=briefing.notes)
        return ContentRequest(subject=template.name, origin=SubjectOrigin.TEMPLATE)

    def _pick_template(self) -> Optional[PromptTemplate]:
        templates = self._scheduler.get_templates()
        return random.choice(templates) if templates else None

    async def _fail(self, post_id: str, error: str, message: str) -> None:
        logger.error("Post %s falhou: %s", post_id, error)
        await self._storage.save_error(post_id, error)
        await self._storage.update_status(post_id, status=PostStatus.FAILED)
        await self._telegram.notify(message)

    async def _run_pipeline(
        self, template: PromptTemplate, request: ContentRequest, schedule_id: Optional[str] = None
    ) -> None:
        max_attempts = self._settings.max_redo_attempts
        post = Post(id=str(uuid.uuid4()), template_id=template.id, schedule_id=schedule_id, max_attempts=max_attempts)
        short_id = post.id[:8]
        await self._storage.save_post(post)
        logger.info("Pipeline iniciado: post=%s assunto='%s' origem=%s", post.id, request.subject, request.origin.value)

        try:
            research = await self._research.run(request)
        except MarketResearchError as exc:
            await self._fail(post.id, f"market_research: {exc}", f"❌ Pesquisa de mercado falhou para `{short_id}`:\n`{exc}`")
            return

        instruction = ""
        for attempt in range(1, max_attempts + 1):
            post.attempt = attempt
            logger.info("Pipeline attempt %d/%d for post %s", attempt, max_attempts, post.id)
            try:
                composed = await self._generate_and_compose(post, template, request, research, instruction)
            except Exception as exc:
                await self._fail(post.id, str(exc), f"❌ Falha ao gerar post `{short_id}`:\n`{exc}`")
                return

            post = post.model_copy(update={
                "status": PostStatus.AWAITING_APPROVAL,
                "images": composed.images,
                "composed_image_paths": composed.composed_image_paths,
                "caption": composed.caption,
                "hashtags": composed.hashtags,
                "total_cost_usd": composed.total_cost_usd,
            })
            await self._storage.save_post(post)

            try:
                post.telegram_message_id = await self._telegram.send_preview(post)
            except Exception as exc:
                await self._fail(post.id, f"telegram_preview: {exc}", f"❌ Falha ao enviar preview do post `{short_id}`.")
                return
            await self._storage.update_status(post.id, telegram_message_id=post.telegram_message_id)

            approval = await self._telegram.await_approval(post.id)
            if approval == ApprovalStatus.APPROVED:
                await self._publish(post)
                return
            if approval != ApprovalStatus.REDO:
                await self._storage.update_status(post.id, status=PostStatus.DISCARDED, approval_status=approval)
                logger.info("Post %s encerrado: %s", post.id, approval.value)
                return
            if attempt == max_attempts:
                await self._telegram.notify(f"⚠️ Post `{short_id}` atingiu o máximo de {max_attempts} tentativas.")
                await self._storage.update_status(post.id, status=PostStatus.DISCARDED, approval_status=ApprovalStatus.REDO)
                return
            instruction = await self._ask_redo_instruction(post.id)
            await self._telegram.notify(f"🔄 Regenerando post (tentativa {attempt + 1}/{max_attempts})...")

    async def _ask_redo_instruction(self, post_id: str) -> str:
        future = self._conversation_handler.register_answer(post_id)
        question_id = await self._telegram.notify(
            f"✍️ O que você quer que eu altere no post `{post_id[:8]}`? (responda *a esta mensagem*)"
        )
        self._conversation_handler.link_question(post_id, question_id)
        try:
            answer = await asyncio.wait_for(future, timeout=float(self._settings.telegram_approval_timeout))
        except asyncio.TimeoutError:
            self._conversation_handler.cancel_answer(post_id)
            logger.info("Sem resposta de redo para post %s — regenerando sem instrução.", post_id)
            return ""
        logger.info("Instrução de redo para post %s: %.80s", post_id, answer)
        return answer

    async def _generate_and_compose(
        self,
        post: Post,
        template: PromptTemplate,
        request: ContentRequest,
        research: MarketResearch,
        instruction: str,
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
        return await self._post_composer.compose(
            images=images,
            template=template,
            post_id=post.id,
            brand=self._brand,
            research=research,
            subject=request.subject,
            instruction=instruction,
        )

    async def _publish_composed(self, composed: ComposedPost) -> None:
        await self._storage.save_post(composed)
        await self._publish(composed)

    async def _publish(self, post: Post) -> None:
        post.approved_at = datetime.now(timezone.utc)
        await self._storage.update_status(
            post.id,
            status=PostStatus.PUBLISHING,
            approval_status=ApprovalStatus.APPROVED,
            approved_at=post.approved_at,
        )

        result = await self._publisher.publish_carousel(post)
        if not result.success:
            await self._storage.update_status(post.id, status=PostStatus.FAILED, error=result.error)
            await self._telegram.notify(f"❌ Falha ao publicar post `{post.id[:8]}`:\n`{result.error}`")
            logger.error("Post %s publish failed: %s", post.id, result.error)
            return

        await self._storage.update_status(
            post.id,
            status=PostStatus.PUBLISHED,
            approval_status=ApprovalStatus.PUBLISHED,
            instagram_media_id=result.media_id,
            published_at=datetime.now(timezone.utc),
        )
        await self._telegram.notify(f"✅ Post `{post.id[:8]}` publicado com sucesso!\nMedia ID: `{result.media_id}`")
        logger.info("Post %s published, media_id=%s", post.id, result.media_id)


async def _main() -> None:
    settings = get_settings()
    setup_logger("src", level=settings.log_level, log_file=settings.log_file)
    agent = InstagramAgent(settings)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, agent.request_stop)
        except NotImplementedError:
            pass
    try:
        await agent.run()
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(_main())
