from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..domain.models.creation import CreationMode
from ..utils.logger import get_logger

logger = get_logger(__name__)


def build_creation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Ficou bom", callback_data="create:accept"),
        InlineKeyboardButton("🔁 Outra opção", callback_data="create:another"),
    ], [
        InlineKeyboardButton("✍️ Ajustar", callback_data="create:adjust"),
        InlineKeyboardButton("❌ Cancelar", callback_data="create:cancel"),
    ]])


def build_creation_final_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprovar e publicar", callback_data="create:publish"),
    ], [
        InlineKeyboardButton("✍️ Ajustar legenda", callback_data="create:caption"),
        InlineKeyboardButton("❌ Descartar", callback_data="create:discard"),
    ]])


def build_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Foto limpa", callback_data="create:mode:clean"),
        InlineKeyboardButton("Banner", callback_data="create:mode:banner"),
        InlineKeyboardButton("Deixa a IA decidir", callback_data="create:mode:auto"),
    ]])


class CreationHandler:
    def __init__(self, allowed_chat_ids: list[int], creation_service):
        self._allowed = allowed_chat_ids
        self._svc = creation_service

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        chat_id = query.message.chat_id if query.message else None
        if chat_id not in self._allowed:
            await query.answer("Não autorizado.")
            return
        await query.answer()
        data = query.data
        if data.startswith("create:mode:"):
            mode = data.split(":", 2)[2]
            await self._svc.set_mode(chat_id, CreationMode(mode))
            return
        action = data.split(":", 1)[1]
        routes = {
            "accept": self._svc.accept_image,
            "another": self._svc.another_option,
            "adjust": self._svc.request_adjustment,
            "cancel": self._svc.cancel,
            "publish": self._svc.publish,
            "caption": self._svc.request_caption_adjustment,
            "discard": self._svc.cancel,
        }
        handler = routes.get(action)
        if handler is not None:
            await handler(chat_id)
