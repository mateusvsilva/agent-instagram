import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..utils.logger import get_logger
from .access import AccessPolicy

logger = get_logger(__name__)


class ConversationHandler:
    def __init__(self, access: AccessPolicy, creation_service=None):
        self._access = access
        self._creation_service = creation_service
        self._pending_answers: dict[str, asyncio.Future] = {}
        self._question_to_post: dict[str, str] = {}

    def register_answer(self, post_id: str) -> asyncio.Future:
        future = asyncio.get_running_loop().create_future()
        self._pending_answers[post_id] = future
        return future

    def link_question(self, post_id: str, question_message_id: Optional[str]) -> None:
        if question_message_id is not None:
            self._question_to_post[question_message_id] = post_id

    def cancel_answer(self, post_id: str) -> None:
        future = self._pending_answers.pop(post_id, None)
        if future and not future.done():
            future.cancel()
        self._forget_question(post_id)

    def _forget_question(self, post_id: str) -> None:
        self._question_to_post = {m: p for m, p in self._question_to_post.items() if p != post_id}

    def _open_posts(self) -> list[str]:
        return [pid for pid, fut in self._pending_answers.items() if not fut.done()]

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._access.allows(update):
            return
        chat = update.effective_chat
        if not update.message or not update.message.text:
            return
        text = update.message.text.strip()
        if not text:
            return

        if self._creation_service is not None and self._creation_service.has_active_session(chat.id):
            await self._creation_service.handle_text(chat.id, text)
            return

        post_id = self._resolve_answer_target(update)
        if post_id is not None:
            future = self._pending_answers.pop(post_id)
            self._forget_question(post_id)
            future.set_result(text)
            logger.info("Resposta de redo recebida para post %s: %.60s", post_id, text)
            return

        if self._open_posts():
            await update.message.reply_text(
                "❓ Há mais de um post aguardando ajuste. Responda *à pergunta* do post "
                "específico usando o recurso de responder (reply) do Telegram.",
                parse_mode="Markdown",
            )
            return

        await update.message.reply_text("Para gerar um post use /post <assunto>, ou /criar para criar conversando.")

    def _resolve_answer_target(self, update: Update) -> Optional[str]:
        open_posts = self._open_posts()
        reply = update.message.reply_to_message
        if reply is not None:
            target = self._question_to_post.get(str(reply.message_id))
            if target in open_posts:
                return target
        return open_posts[0] if len(open_posts) == 1 else None
