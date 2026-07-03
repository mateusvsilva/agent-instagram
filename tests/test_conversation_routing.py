from unittest.mock import AsyncMock, MagicMock
from src.handlers.conversation_handler import ConversationHandler


def _update(text, chat_id=42):
    u = MagicMock()
    u.effective_chat = MagicMock(); u.effective_chat.id = chat_id
    u.message = MagicMock(); u.message.text = text
    u.message.reply_to_message = None
    u.message.reply_text = AsyncMock()
    return u


async def test_active_session_captures_text():
    svc = MagicMock(); svc.has_active_session.return_value = True; svc.handle_text = AsyncMock()
    subject_cb = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], subject_callback=subject_cb, creation_service=svc)
    await h.handle_message(_update("mais escuro"), MagicMock())
    svc.handle_text.assert_awaited_with(42, "mais escuro")
    subject_cb.assert_not_awaited()


async def test_no_session_falls_back_to_subject():
    svc = MagicMock(); svc.has_active_session.return_value = False; svc.handle_text = AsyncMock()
    subject_cb = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], subject_callback=subject_cb, creation_service=svc)
    await h.handle_message(_update("poste sobre engrenagens"), MagicMock())
    svc.handle_text.assert_not_awaited()
    subject_cb.assert_awaited()
