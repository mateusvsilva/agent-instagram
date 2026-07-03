from unittest.mock import AsyncMock, MagicMock
from src.handlers.creation_handler import (
    CreationHandler, build_creation_keyboard, build_creation_final_keyboard, build_mode_keyboard,
)


def test_keyboards_callback_data():
    kb = build_creation_keyboard()
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert {"create:accept", "create:another", "create:adjust", "create:cancel"} <= set(data)
    fkb = build_creation_final_keyboard()
    fdata = [b.callback_data for row in fkb.inline_keyboard for b in row]
    assert {"create:publish", "create:caption", "create:discard"} <= set(fdata)
    mkb = build_mode_keyboard()
    mdata = [b.callback_data for row in mkb.inline_keyboard for b in row]
    assert {"create:mode:clean", "create:mode:banner", "create:mode:auto"} <= set(mdata)


def _query(data, chat_id=42):
    q = MagicMock()
    q.data = data
    q.answer = AsyncMock()
    q.message = MagicMock(); q.message.chat_id = chat_id
    update = MagicMock(); update.callback_query = q
    return update


async def test_accept_routes_to_service():
    svc = MagicMock(); svc.accept_image = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[42], creation_service=svc)
    await h.handle_callback(_query("create:accept"), MagicMock())
    svc.accept_image.assert_awaited_with(42)


async def test_mode_routes_with_enum():
    from src.domain.models.creation import CreationMode
    svc = MagicMock(); svc.set_mode = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[42], creation_service=svc)
    await h.handle_callback(_query("create:mode:banner"), MagicMock())
    svc.set_mode.assert_awaited_with(42, CreationMode.BANNER)


async def test_unauthorized_ignored():
    svc = MagicMock(); svc.accept_image = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[999], creation_service=svc)
    await h.handle_callback(_query("create:accept", chat_id=42), MagicMock())
    svc.accept_image.assert_not_awaited()
