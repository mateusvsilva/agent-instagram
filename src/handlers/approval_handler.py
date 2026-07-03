import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Awaitable

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..domain.models.enums import ApprovalStatus
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..services.telegram_bot import TelegramBotService

logger = get_logger(__name__)

CALLBACK_APPROVE = "approve"
CALLBACK_REJECT = "reject"
CALLBACK_REDO = "redo"

ApprovalCallback = Callable[[str, ApprovalStatus], Awaitable[None]]


def build_approval_keyboard(post_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprovar", callback_data=f"{CALLBACK_APPROVE}:{post_id}"),
            InlineKeyboardButton("❌ Rejeitar", callback_data=f"{CALLBACK_REJECT}:{post_id}"),
            InlineKeyboardButton("🔄 Refazer", callback_data=f"{CALLBACK_REDO}:{post_id}"),
        ]
    ])


class ApprovalHandler:
    def __init__(self, allowed_chat_ids: list[int]):
        self._allowed_chat_ids = allowed_chat_ids
        self._pending: dict[str, asyncio.Future] = {}

    def register_pending(self, post_id: str) -> asyncio.Future:
        loop = self._resolve_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[post_id] = future
        return future

    @staticmethod
    def _resolve_event_loop() -> asyncio.AbstractEventLoop:
        """Return the loop the pending future should be bound to.

        In production ``register_pending`` is always called from within
        ``await_approval`` (a coroutine), so a running loop exists and the
        future must be bound to it for ``asyncio.wait_for`` to resolve it.
        When invoked outside a running loop (e.g. synchronous callers), we
        fall back to the current event loop, creating one if necessary —
        avoiding the deprecated ``get_event_loop`` behaviour on Python 3.11+.
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()

    def cancel_pending(self, post_id: str) -> None:
        future = self._pending.pop(post_id, None)
        if future and not future.done():
            future.set_result(ApprovalStatus.EXPIRED)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return

        if query.message and query.message.chat_id not in self._allowed_chat_ids:
            await query.answer("Não autorizado.")
            return

        await query.answer()

        action, post_id = query.data.split(":", 1)
        status_map = {
            CALLBACK_APPROVE: ApprovalStatus.APPROVED,
            CALLBACK_REJECT: ApprovalStatus.REJECTED,
            CALLBACK_REDO: ApprovalStatus.REDO,
        }
        status = status_map.get(action)
        if not status:
            return

        label_map = {
            ApprovalStatus.APPROVED: "✅ Aprovado",
            ApprovalStatus.REJECTED: "❌ Rejeitado",
            ApprovalStatus.REDO: "🔄 Refazendo...",
        }
        label = label_map.get(status, str(status))

        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"{label} por {query.from_user.first_name}.")
        except Exception as exc:
            logger.debug("Could not edit approval message: %s", exc)

        future = self._pending.get(post_id)
        if future and not future.done():
            future.set_result(status)
            self._pending.pop(post_id, None)
            logger.info("Approval resolved: post=%s status=%s by user=%s",
                        post_id, status, query.from_user.id)
        else:
            logger.warning("No pending future for post_id=%s (may have timed out)", post_id)
