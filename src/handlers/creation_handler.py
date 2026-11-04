from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..domain.models.creation import CreationMode
from .access import AccessPolicy


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
    def __init__(self, access: AccessPolicy, creation_service):
        self._access = access
        self._svc = creation_service
        self._routes = {
            "accept": creation_service.accept_image,
            "another": creation_service.another_option,
            "adjust": creation_service.request_adjustment,
            "cancel": creation_service.cancel,
            "publish": creation_service.publish,
            "caption": creation_service.request_caption_adjustment,
            "discard": creation_service.cancel,
        }

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        if query.message is None or not self._access.allows(update):
            await query.answer("Não autorizado.")
            return
        chat_id = query.message.chat_id
        await query.answer()
        action, _, arg = query.data.removeprefix("create:").partition(":")
        if action == "mode":
            try:
                mode = CreationMode(arg)
            except ValueError:
                return
            await self._svc.set_mode(chat_id, mode)
            return
        handler = self._routes.get(action)
        if handler is not None:
            await handler(chat_id)
