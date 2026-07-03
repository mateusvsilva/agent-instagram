from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.creation_service import CreationService
from src.domain.models.creation import CreationState


def _telegram():
    t = MagicMock()
    t.notify = AsyncMock(return_value="1")
    t.send_mode_prompt = AsyncMock()
    t.send_creation_preview = AsyncMock()
    t.send_creation_final_preview = AsyncMock()
    return t


def _settings():
    s = MagicMock()
    s.creation_max_rounds = 12
    s.creation_session_timeout = 1800
    return s


def make_service(brain_available=True, telegram=None, **over):
    brain = MagicMock(); brain.available = brain_available
    svc = CreationService(
        brain=brain,
        art_director=over.get("art_director", MagicMock()),
        image_generator=over.get("image_generator", MagicMock()),
        brand=over.get("brand", MagicMock()),
        budget=over.get("budget", MagicMock()),
        post_composer=over.get("post_composer", MagicMock()),
        telegram=telegram or _telegram(),
        settings=_settings(),
    )
    return svc


async def test_start_blocks_without_brain():
    t = _telegram()
    svc = make_service(brain_available=False, telegram=t)
    await svc.start(123)
    assert svc.has_active_session(123) is False
    t.notify.assert_awaited()


async def test_start_creates_session_and_greets():
    t = _telegram()
    svc = make_service(telegram=t)
    await svc.start(123)
    assert svc.has_active_session(123) is True
    assert svc._sessions[123].state == CreationState.AWAITING_BRIEF


async def test_cancel_removes_session():
    svc = make_service()
    await svc.start(123)
    await svc.cancel(123)
    assert svc.has_active_session(123) is False


import uuid as _uuid
from pathlib import Path
from PIL import Image
from src.domain.models.creation import CreationMode
from src.domain.models.post import GeneratedImage
from src.utils.cost_tracker import BudgetTracker


def _fake_image_generator(tmp_path: Path):
    gen = MagicMock()
    gen.estimate_cost.return_value = 0.04

    async def _generate(template, post_id, count=1, image_brief="", subject=""):
        p = tmp_path / post_id / "raw_0.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 1280), (50, 60, 70)).save(p, format="PNG")
        return [GeneratedImage(id=str(_uuid.uuid4()), post_id=post_id, file_path=str(p),
                               prompt_used=template.prompt, cost_usd=0.04)]
    gen.generate = AsyncMock(side_effect=_generate)
    return gen


def _art():
    a = MagicMock()
    a.build_image_prompt = AsyncMock(return_value="english prompt v1")
    a.revise_image_prompt = AsyncMock(return_value="english prompt v2")
    return a


async def test_brief_then_mode_generates_one_image(tmp_path):
    t = _telegram()
    brand = MagicMock(); brand.image_brief.return_value = "marca"
    svc = make_service(telegram=t, art_director=_art(),
                       image_generator=_fake_image_generator(tmp_path),
                       brand=brand, budget=BudgetTracker(10, 100, 0.8))
    await svc.start(7)
    await svc.handle_text(7, "uma engrenagem")          # vira brief, pede modo
    t.send_mode_prompt.assert_awaited()
    await svc.set_mode(7, CreationMode.CLEAN)            # dispara 1ª geração
    s = svc._sessions[7]
    assert s.state == CreationState.ITERATING
    assert s.rounds == 1 and s.current_image_path
    t.send_creation_preview.assert_awaited()


async def test_feedback_revises_and_regenerates(tmp_path):
    t = _telegram(); art = _art()
    svc = make_service(telegram=t, art_director=art,
                       image_generator=_fake_image_generator(tmp_path),
                       brand=MagicMock(), budget=BudgetTracker(10, 100, 0.8))
    await svc.start(7); await svc.handle_text(7, "engrenagem"); await svc.set_mode(7, CreationMode.AUTO)
    await svc.request_adjustment(7)
    assert svc._sessions[7].state == CreationState.AWAITING_FEEDBACK
    await svc.handle_text(7, "mais escuro")
    art.revise_image_prompt.assert_awaited_with("english prompt v1", "mais escuro")
    assert svc._sessions[7].rounds == 2


async def test_budget_stop_blocks_generation(tmp_path):
    t = _telegram()
    budget = MagicMock(); budget.can_spend.return_value = False
    gen = _fake_image_generator(tmp_path)
    svc = make_service(telegram=t, art_director=_art(), image_generator=gen,
                       brand=MagicMock(), budget=budget)
    await svc.start(7); await svc.handle_text(7, "x"); await svc.set_mode(7, CreationMode.AUTO)
    gen.generate.assert_not_awaited()
    t.notify.assert_awaited()


from src.domain.models.post import ComposedPost
from src.domain.models.creation import CreationState as CS


def _post_composer(post_id="p"):
    pc = MagicMock()
    async def _compose(images, template, post_id, brand=None, research=None, subject="", instruction=""):
        return ComposedPost(id=post_id, template_id="conversational",
                            composed_image_paths=["x.jpg"], caption="legenda " + instruction,
                            images=list(images), total_cost_usd=0.04)
    pc.compose = AsyncMock(side_effect=_compose)
    return pc


async def _ready_session(tmp_path):
    t = _telegram()
    svc = make_service(telegram=t, art_director=_art(),
                       image_generator=_fake_image_generator(tmp_path),
                       brand=MagicMock(), budget=BudgetTracker(10, 100, 0.8),
                       post_composer=_post_composer())
    await svc.start(7); await svc.handle_text(7, "engrenagem"); await svc.set_mode(7, CreationMode.AUTO)
    return svc, t


async def test_accept_composes_and_previews(tmp_path):
    svc, t = await _ready_session(tmp_path)
    await svc.accept_image(7)
    assert svc._sessions[7].state == CS.AWAITING_PUBLISH
    assert svc._sessions[7].composed is not None
    t.send_creation_final_preview.assert_awaited()


async def test_publish_calls_on_complete_and_ends(tmp_path):
    svc, t = await _ready_session(tmp_path)
    await svc.accept_image(7)
    received = {}
    async def _done(composed):
        received["c"] = composed
    svc.on_complete = _done
    await svc.publish(7)
    assert received["c"].caption.startswith("legenda")
    assert svc.has_active_session(7) is False
