from unittest.mock import AsyncMock, MagicMock

from src.handlers.command_handler import CommandHandler
from src.handlers.conversation_handler import ConversationHandler


def _update(text, chat_id=42):
    u = MagicMock()
    u.effective_chat = MagicMock()
    u.effective_chat.id = chat_id
    u.message = MagicMock()
    u.message.text = text
    u.message.reply_to_message = None
    u.message.reply_text = AsyncMock()
    return u


async def test_active_session_captures_text():
    svc = MagicMock()
    svc.has_active_session.return_value = True
    svc.handle_text = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], creation_service=svc)
    await h.handle_message(_update("mais escuro"), MagicMock())
    svc.handle_text.assert_awaited_with(42, "mais escuro")


async def test_free_text_does_not_generate_post():
    svc = MagicMock()
    svc.has_active_session.return_value = False
    svc.handle_text = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], creation_service=svc)
    update = _update("obrigado!")
    await h.handle_message(update, MagicMock())
    svc.handle_text.assert_not_awaited()
    assert "/post" in update.message.reply_text.call_args.args[0]


def _command_handler(post_cb):
    return CommandHandler([42], MagicMock(), MagicMock(), AsyncMock(), AsyncMock(), post_cb)


async def test_post_command_triggers_with_subject():
    post_cb = AsyncMock()
    await _command_handler(post_cb).cmd_post(_update("/post engrenagens sob medida"), MagicMock(args=["engrenagens", "sob", "medida"]))
    post_cb.assert_awaited_once_with("engrenagens sob medida")


async def test_post_command_without_subject_shows_usage():
    post_cb = AsyncMock()
    update = _update("/post")
    await _command_handler(post_cb).cmd_post(update, MagicMock(args=[]))
    post_cb.assert_not_awaited()
    assert "Uso: /post" in update.message.reply_text.call_args.args[0]


async def test_post_command_ignores_unauthorized_chat():
    post_cb = AsyncMock()
    await _command_handler(post_cb).cmd_post(_update("/post x", chat_id=7), MagicMock(args=["x"]))
    post_cb.assert_not_awaited()
