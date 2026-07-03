import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.template import DalleParams, PromptTemplate
from src.utils.cost_tracker import BudgetTracker


def _make_settings(tmp_path: Path):
    s = MagicMock()
    s.openai_api_key = "sk-test"
    s.dalle_model = "dall-e-3"
    s.dalle_default_quality = "hd"
    s.images_dir = tmp_path / "images"
    s.daily_budget_usd = 10.0
    s.monthly_budget_usd = 100.0
    s.budget_alert_threshold = 0.8
    return s


def _make_template() -> PromptTemplate:
    return PromptTemplate(
        id="test_tpl",
        name="Test",
        prompt="A {style} scene with {mood} atmosphere",
        variables={"style": ["realistic"], "mood": ["calm"]},
        caption_template="Test caption",
        hashtag_pool=["#test"],
        image_count=2,
        dalle_params=DalleParams(size="1024x1024", quality="hd", style="vivid"),
    )


@pytest.fixture
def budget(tmp_path):
    return BudgetTracker(daily_limit=10.0, monthly_limit=100.0)


async def test_generate_calls_openai_and_saves(tmp_path: Path, budget: BudgetTracker):
    from src.services.image_generator import ImageGeneratorService

    settings = _make_settings(tmp_path)
    service = ImageGeneratorService(settings=settings, budget_tracker=budget)
    template = _make_template()
    post_id = str(uuid.uuid4())

    fake_image_bytes = b"\xff\xd8\xff" + b"\x00" * 100

    mock_response = MagicMock()
    mock_response.data = [MagicMock(url="https://fake.dalle.url/img.jpg")]

    with (
        patch.object(service._client.images, "generate", new=AsyncMock(return_value=mock_response)),
        patch("httpx.AsyncClient") as mock_http,
    ):
        mock_http_instance = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_http_instance
        mock_http_instance.get.return_value = MagicMock(
            content=fake_image_bytes, raise_for_status=MagicMock()
        )

        with patch("asyncio.sleep", new=AsyncMock()):
            images = await service.generate(template, post_id, count=2)

    assert len(images) == 2
    assert all(img.post_id == post_id for img in images)
    assert all(img.cost_usd == 0.08 for img in images)
    assert budget.daily_spent == pytest.approx(0.16, abs=0.001)


async def test_budget_exceeded_raises(tmp_path: Path):
    from src.services.image_generator import ImageGeneratorService

    settings = _make_settings(tmp_path)
    budget = BudgetTracker(daily_limit=0.05, monthly_limit=1.0)
    service = ImageGeneratorService(settings=settings, budget_tracker=budget)
    template = _make_template()

    with pytest.raises(RuntimeError, match="Budget exceeded"):
        await service.generate(template, "post123", count=2)


def test_estimate_cost(tmp_path: Path, budget: BudgetTracker):
    from src.services.image_generator import ImageGeneratorService

    settings = _make_settings(tmp_path)
    service = ImageGeneratorService(settings=settings, budget_tracker=budget)
    assert service.estimate_cost(4, "hd") == pytest.approx(0.32)
    assert service.estimate_cost(4, "standard") == pytest.approx(0.16)


def test_prompt_variable_substitution(tmp_path: Path, budget: BudgetTracker):
    from src.services.image_generator import ImageGeneratorService

    settings = _make_settings(tmp_path)
    service = ImageGeneratorService(settings=settings, budget_tracker=budget)
    template = _make_template()

    prompt = service._build_prompt(template)
    assert "{style}" not in prompt
    assert "{mood}" not in prompt
    assert "realistic" in prompt
    assert "calm" in prompt
