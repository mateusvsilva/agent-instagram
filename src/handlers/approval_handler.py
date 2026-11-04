import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..domain.models.enums import ApprovalStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)

CALLBACK_APPROVE = "approve"
CALLBACK_REJECT = "reject"
CALLBACK_REDO = "redo"

_STATUS_BY_ACTION = {
    CALLBACK_APPROVE: ApprovalStatus.APPROVED,
    CALLBACK_REJECT: ApprovalStatus.REJECTED,
    CALLBACK_REDO: ApprovalStatus.REDO,
}
_LABELS = {
    ApprovalStatus.APPROVED: "✅ Aprovado",
    ApprovalStatus.REJECTED: "❌ Rejeitado",
    ApprovalStatus.REDO: "🔄 Refazendo...",
}


def build_approval_keyboard(post_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprovar", callback_data=f"{CALLBACK_APPROVE}:{post_id}"),
        InlineKeyboardButton("❌ Rejeitar", callback_data=f"{CALLBACK_REJECT}:{post_id}"),
        InlineKeyboardButton("🔄 Refazer", callback_data=f"{CALLBACK_REDO}:{post_id}"),
    ]])


class ApprovalHandler:
    def __init__(self, allowed_chat_ids: list[int]):
        self._allowed_chat_ids = allowed_chat_ids
        self._pending: dict[str, asyncio.Future] = {}

    def register_pending(self, post_id: str) -> asyncio.Future:
        future = asyncio.get_running_loop().create_future()
        self._pending[post_id] = future
        return future

    def cancel_pending(self, post_id: str) -> None:
        future = self._pending.pop(post_id, None)
        if future and not future.done():
            future.set_result(ApprovalStatus.EXPIRED)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return

        chat_id = query.message.chat_id if query.message else None
        if chat_id not in self._allowed_chat_ids:
            await query.answer("Não autorizado.")
            return

        action, _, post_id = query.data.partition(":")
        status = _STATUS_BY_ACTION.get(action)
        future = self._pending.get(post_id) if status else None
        if future is None or future.done():
            await query.answer("Este post não está mais aguardando aprovação.")
            return

        await query.answer()
        self._pending.pop(post_id, None)
        future.set_result(status)
        logger.info("Approval resolved: post=%s status=%s by user=%s", post_id, status, query.from_user.id)

        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"{_LABELS[status]} por {query.from_user.first_name}.")
        except Exception as exc:
            logger.debug("Could not edit approval message: %s", exc)
