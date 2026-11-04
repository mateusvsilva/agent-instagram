import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from tests.helpers import allow, callback_update

import pytest
from pydantic import ValidationError
from telegram.error import BadRequest

from src.config import Settings
from src.domain.models.creation import CreationMode
from src.domain.models.enums import ApprovalStatus, PostStatus
from src.domain.models.post import Post
from src.handlers.access import AccessPolicy
from src.handlers.approval_handler import ApprovalHandler
from src.services.creation_service import CreationService
from src.services.storage import StorageService
from src.services.telegram_bot import TelegramBotService
from src.utils.cost_tracker import BudgetTracker


@pytest.fixture
async def storage(tmp_path):
    svc = StorageService(db_path=tmp_path / "t.db")
    await svc.initialize()
    return svc


async def test_update_status_rejects_unknown_columns(storage):
    post = Post(id=str(uuid.uuid4()), template_id="t")
    await storage.save_post(post)
    with pytest.raises(ValueError):
        await storage.update_status(post.id, **{"error = 'x', caption": "y"})


async def test_expire_pending_marks_leftovers(storage):
    pending = Post(id="a", template_id="t")
    done = Post(id="b", template_id="t", status=PostStatus.PUBLISHED, approval_status=ApprovalStatus.PUBLISHED)
    await storage.save_post(pending)
    await storage.save_post(done)
    assert await storage.expire_pending() == 1
    assert (await storage.get_post("a")).approval_status == ApprovalStatus.EXPIRED
    assert (await storage.get_post("b")).approval_status == ApprovalStatus.PUBLISHED


async def test_budget_spend_is_persisted_and_restorable(storage):
    budget = BudgetTracker(daily_limit=10, monthly_limit=100, ledger=storage)
    await budget.spend(0.04, "sessao-descartada")
    await budget.spend(0.04, "sessao-descartada")
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert await storage.get_cost_since(since) == pytest.approx(0.08)
    assert await storage.get_cost_since(datetime.now(timezone.utc) + timedelta(minutes=1)) == 0


async def test_budget_spend_survives_ledger_failure():
    ledger = MagicMock(record_cost=AsyncMock(side_effect=OSError("disk full")))
    budget = BudgetTracker(daily_limit=10, monthly_limit=100, ledger=ledger)
    await budget.spend(0.5, "p")
    assert budget.daily_spent == pytest.approx(0.5)


@pytest.mark.parametrize("field", ["BUFFER_SCHEDULING_MODE", "BUFFER_INSTAGRAM_POST_TYPE"])
def test_settings_reject_graphql_injection(field, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv(field, "addToQueue } evil: {")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


async def test_callback_for_unknown_post_is_not_acknowledged_as_approved():
    handler = ApprovalHandler(allow(1))
    query = MagicMock()
    query.data = "approve:missing"
    query.answer = AsyncMock()
    query.message = MagicMock(chat_id=1)
    query.edit_message_reply_markup = AsyncMock()
    update = callback_update(query)
    await handler.handle_callback(update, MagicMock())
    query.edit_message_reply_markup.assert_not_awaited()
    query.answer.assert_awaited_once_with("Este post não está mais aguardando aprovação.")


async def test_notify_falls_back_to_plain_text_on_bad_markdown():
    settings = MagicMock(telegram_chat_id=1, telegram_approval_timeout=10)
    svc = TelegramBotService(settings=settings, approval_handler=ApprovalHandler(allow(1)))
    calls = []

    async def _send(**kw):
        calls.append(kw)
        if kw["parse_mode"]:
            raise BadRequest("can't parse entities")
        return MagicMock(message_id=7)

    svc._app = MagicMock()
    svc._app.bot.send_message = _send
    assert await svc.notify("erro com_underscore") == "7"
    assert [c["parse_mode"] for c in calls] == ["Markdown", None]


def _creation(timeout=1800):
    telegram = MagicMock(notify=AsyncMock(), send_mode_prompt=AsyncMock())
    settings = MagicMock(creation_session_timeout=timeout, creation_max_rounds=12)
    return CreationService(
        brain=MagicMock(available=True), art_director=MagicMock(), image_generator=MagicMock(),
        brand=MagicMock(), budget=MagicMock(), post_composer=MagicMock(), telegram=telegram, settings=settings,
    )


async def test_creation_session_expires():
    svc = _creation(timeout=60)
    await svc.start(5)
    svc._sessions[5].updated_at -= timedelta(seconds=61)
    assert svc.has_active_session(5) is False


def test_infer_mode_sem_texto_is_clean():
    assert CreationService._infer_mode("sem texto, só a peça") == CreationMode.CLEAN
    assert CreationService._infer_mode("banner com texto") == CreationMode.BANNER


async def test_group_member_not_in_allowlist_cannot_approve():
    handler = ApprovalHandler(AccessPolicy([-100], [111]))
    future = handler.register_pending("p1")
    query = MagicMock(data="approve:p1", answer=AsyncMock(), message=MagicMock(chat_id=-100))
    await handler.handle_callback(callback_update(query, user_id=222), MagicMock())
    assert not future.done()
    query.answer.assert_awaited_once_with("Não autorizado.")


def test_allowed_user_ids_default_to_private_chat_owner(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "555")
    assert Settings(_env_file=None).allowed_user_ids == [555]
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1, 2")
    assert Settings(_env_file=None).allowed_user_ids == [1, 2]
