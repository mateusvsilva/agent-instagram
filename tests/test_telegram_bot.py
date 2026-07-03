import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.handlers.approval_handler import ApprovalHandler, build_approval_keyboard, CALLBACK_APPROVE, CALLBACK_REJECT, CALLBACK_REDO
from src.domain.models.enums import ApprovalStatus


def test_build_keyboard_has_three_buttons():
    keyboard = build_approval_keyboard("post-abc")
    buttons = keyboard.inline_keyboard[0]
    assert len(buttons) == 3
    data_values = [b.callback_data for b in buttons]
    assert any(CALLBACK_APPROVE in d for d in data_values)
    assert any(CALLBACK_REJECT in d for d in data_values)
    assert any(CALLBACK_REDO in d for d in data_values)


async def test_approval_handler_resolves_approve():
    handler = ApprovalHandler(allowed_chat_ids=[12345])
    post_id = str(uuid.uuid4())

    future = handler.register_pending(post_id)

    query = MagicMock()
    query.data = f"{CALLBACK_APPROVE}:{post_id}"
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 12345
    query.message.reply_text = AsyncMock()
    query.from_user = MagicMock(first_name="Tester", id=12345)

    update = MagicMock()
    update.callback_query = query

    await handler.handle_callback(update, MagicMock())

    assert future.done()
    assert future.result() == ApprovalStatus.APPROVED


async def test_approval_handler_resolves_reject():
    handler = ApprovalHandler(allowed_chat_ids=[12345])
    post_id = str(uuid.uuid4())
    future = handler.register_pending(post_id)

    query = MagicMock()
    query.data = f"{CALLBACK_REJECT}:{post_id}"
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 12345
    query.message.reply_text = AsyncMock()
    query.from_user = MagicMock(first_name="Tester", id=12345)

    update = MagicMock()
    update.callback_query = query

    await handler.handle_callback(update, MagicMock())
    assert future.result() == ApprovalStatus.REJECTED


async def test_approval_timeout_returns_expired():
    handler = ApprovalHandler(allowed_chat_ids=[12345])
    post_id = str(uuid.uuid4())

    settings = MagicMock()
    settings.telegram_bot_token = "fake"
    settings.telegram_chat_id = 12345
    settings.telegram_approval_timeout = 1

    from src.services.telegram_bot import TelegramBotService
    svc = TelegramBotService(settings=settings, approval_handler=handler)

    future = handler.register_pending(post_id)
    svc._app = MagicMock()

    status = await svc.await_approval(post_id, timeout=1)
    assert status == ApprovalStatus.EXPIRED


async def test_cancel_pending_sets_expired():
    handler = ApprovalHandler(allowed_chat_ids=[12345])
    post_id = str(uuid.uuid4())
    future = handler.register_pending(post_id)
    handler.cancel_pending(post_id)
    assert future.done()
    assert future.result() == ApprovalStatus.EXPIRED


def test_unauthorized_callback_ignored():
    handler = ApprovalHandler(allowed_chat_ids=[99999])
    post_id = str(uuid.uuid4())
    future = handler.register_pending(post_id)

    query = MagicMock()
    query.data = f"{CALLBACK_APPROVE}:{post_id}"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 11111

    update = MagicMock()
    update.callback_query = query

    asyncio.run(handler.handle_callback(update, MagicMock()))
    assert not future.done()


async def test_send_creation_final_preview_uses_final_keyboard(tmp_path):
    from unittest.mock import AsyncMock, MagicMock
    from PIL import Image
    from src.services.telegram_bot import TelegramBotService
    from src.handlers.approval_handler import ApprovalHandler
    from src.domain.models.post import ComposedPost

    settings = MagicMock()
    settings.telegram_chat_id = 42
    settings.telegram_approval_timeout = 10
    svc = TelegramBotService(settings=settings, approval_handler=ApprovalHandler([42]))

    img = tmp_path / "composed_0.jpg"
    Image.new("RGB", (1080, 1350), (10, 20, 30)).save(img, format="JPEG")
    post = ComposedPost(id="abcd1234", template_id="conversational",
                        composed_image_paths=[str(img)], caption="legenda", total_cost_usd=0.04)

    sent = {}
    bot = MagicMock()
    async def _send_photo(**kw):
        sent.update(kw); return MagicMock(message_id=99)
    bot.send_photo = _send_photo
    svc._app = MagicMock(); svc._app.bot = bot

    mid = await svc.send_creation_final_preview(post)
    assert mid == "99"
    data = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]
    assert "create:publish" in data
