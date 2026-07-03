"""Sessão de criação conversacional de imagem (/criar).

Máquina de estados por chat: conversa (cérebro via ArtDirector) → gera 1 imagem
por rodada (reusa image_generator.generate com template ad-hoc) → ao aprovar,
compõe a legenda (post_composer) e entrega via callback on_complete.
"""
import uuid
from typing import Awaitable, Callable, Optional

from ..domain.models.creation import CreationMode, CreationSession, CreationState
from ..domain.models.post import ComposedPost, GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.logger import get_logger

logger = get_logger(__name__)

OnComplete = Callable[[ComposedPost], Awaitable[None]]


class CreationService:
    def __init__(self, *, brain, art_director, image_generator, brand, budget, post_composer, telegram, settings):
        self._brain = brain
        self._art = art_director
        self._image_generator = image_generator
        self._brand = brand
        self._budget = budget
        self._post_composer = post_composer
        self._telegram = telegram
        self._settings = settings
        self.on_complete: Optional[OnComplete] = None
        self._sessions: dict[int, CreationSession] = {}

    def has_active_session(self, chat_id: int) -> bool:
        s = self._sessions.get(chat_id)
        return s is not None and s.state not in (CreationState.DONE, CreationState.CANCELLED)

    async def start(self, chat_id: int) -> None:
        if not self._brain.available:
            await self._telegram.notify(
                "⚠️ Criação por IA indisponível: configure `BRAIN_PROVIDER`/chave do cérebro."
            )
            return
        if self.has_active_session(chat_id):
            self._sessions.pop(chat_id, None)
            await self._telegram.notify("↺ Recomeçando — a criação anterior foi descartada.")
        self._sessions[chat_id] = CreationSession(chat_id=chat_id, post_id=str(uuid.uuid4()))
        await self._telegram.notify(
            "🎨 Bora criar. O que você quer mostrar?\n"
            "(ex.: 'engrenagem de reposição', 'impressora imprimindo', 'banner: quando vale 3D')"
        )

    async def cancel(self, chat_id: int) -> None:
        if self._sessions.pop(chat_id, None) is not None:
            await self._telegram.notify("❌ Criação cancelada.")

    async def handle_text(self, chat_id: int, text: str) -> None:
        session = self._sessions.get(chat_id)
        if session is None:
            return
        text = text.strip()
        if not text:
            return
        if session.state == CreationState.AWAITING_BRIEF:
            session.brief = text
            session.state = CreationState.AWAITING_FOLLOWUP
            await self._telegram.send_mode_prompt(chat_id)
        elif session.state == CreationState.AWAITING_FOLLOWUP:
            session.mode = self._infer_mode(text)
            session.brief = f"{session.brief}. {text}".strip(". ")
            await self._first_generation(session)
        elif session.state == CreationState.AWAITING_FEEDBACK:
            session.current_prompt = await self._art.revise_image_prompt(session.current_prompt, text)
            await self._generate_round(session)
        elif session.state == CreationState.AWAITING_CAPTION_FEEDBACK:
            await self.adjust_caption(chat_id, text)

    async def set_mode(self, chat_id: int, mode: CreationMode) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.AWAITING_FOLLOWUP:
            return
        session.mode = mode
        await self._first_generation(session)

    async def another_option(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        await self._generate_round(session)

    async def request_adjustment(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        session.state = CreationState.AWAITING_FEEDBACK
        await self._telegram.notify(
            "✍️ O que ajustar? (ex.: 'mais escuro', 'tira o texto', 'fundo de concreto')"
        )

    async def _first_generation(self, session: CreationSession) -> None:
        session.current_prompt = await self._art.build_image_prompt(session.brief, session.mode.value)
        await self._generate_round(session)

    async def _generate_round(self, session: CreationSession) -> None:
        if session.rounds >= self._settings.creation_max_rounds:
            await self._telegram.notify(
                f"⚠️ Limite de {self._settings.creation_max_rounds} rodadas. Use 👍 para aprovar ou ❌ para cancelar."
            )
            return
        if not self._budget.can_spend(self._image_generator.estimate_cost(1)):
            await self._telegram.notify("⚠️ Orçamento atingido — não dá pra gerar mais imagens agora.")
            return
        template = self._build_adhoc_template(session.current_prompt)
        images = await self._image_generator.generate(
            template=template, post_id=session.post_id, count=1,
            image_brief=self._brand.image_brief(), subject="",
        )
        img = images[0]
        session.current_image_path = img.file_path
        session.rounds += 1
        session.total_cost_usd += img.cost_usd
        session.state = CreationState.ITERATING
        note = f"Rodada {session.rounds} · sessão ${session.total_cost_usd:.3f}"
        await self._telegram.send_creation_preview(session.chat_id, img.file_path, note)

    def _build_adhoc_template(self, prompt: str) -> PromptTemplate:
        return PromptTemplate(
            id="conversational", name="Conversational", prompt=prompt,
            variables={}, caption_template="", hashtag_pool=[], image_count=1,
        )

    @staticmethod
    def _infer_mode(text: str) -> CreationMode:
        low = text.lower()
        if "banner" in low or "texto" in low:
            return CreationMode.BANNER
        if "limpa" in low or "foto" in low or "sem texto" in low:
            return CreationMode.CLEAN
        return CreationMode.AUTO

    async def accept_image(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        session.state = CreationState.COMPOSING
        await self._telegram.notify("✍️ Escrevendo a legenda no tom da marca…")
        composed = await self._compose(session, instruction="")
        session.composed = composed
        session.state = CreationState.AWAITING_PUBLISH
        await self._telegram.send_creation_final_preview(composed)

    async def request_caption_adjustment(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.AWAITING_PUBLISH:
            return
        session.state = CreationState.AWAITING_CAPTION_FEEDBACK
        await self._telegram.notify("✍️ O que mudar na legenda?")

    async def adjust_caption(self, chat_id: int, feedback: str) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.composed is None:
            return
        composed = await self._compose(session, instruction=feedback)
        session.composed = composed
        session.state = CreationState.AWAITING_PUBLISH
        await self._telegram.send_creation_final_preview(composed)

    async def publish(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.composed is None:
            return
        composed = session.composed
        session.state = CreationState.DONE
        self._sessions.pop(chat_id, None)
        if self.on_complete is not None:
            await self.on_complete(composed)

    async def _compose(self, session: CreationSession, instruction: str) -> ComposedPost:
        image = GeneratedImage(
            id=str(uuid.uuid4()), post_id=session.post_id,
            file_path=session.current_image_path or "", prompt_used=session.current_prompt,
            cost_usd=0.0,
        )
        return await self._post_composer.compose(
            images=[image], template=self._build_adhoc_template(session.current_prompt),
            post_id=session.post_id, brand=self._brand, subject=session.brief, instruction=instruction,
        )
