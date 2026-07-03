import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.domain.models.post import GeneratedImage
from src.domain.models.template import DalleParams, PromptTemplate


def _make_settings(tmp_path: Path):
    s = MagicMock()
    s.images_dir = tmp_path / "images"
    return s


def _make_template() -> PromptTemplate:
    return PromptTemplate(
        id="tpl1",
        name="Test",
        prompt="Test prompt",
        variables={},
        caption_template="Texto principal da caption. ✨",
        hashtag_pool=["#aiart", "#test", "#instagram"],
        image_count=2,
        dalle_params=DalleParams(),
    )


def _create_fake_image(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1024, 1792), color=(100, 150, 200))
    img.save(path, format="JPEG")
    return path


def _make_generated_image(post_id: str, file_path: str) -> GeneratedImage:
    return GeneratedImage(
        id=str(uuid.uuid4()),
        post_id=post_id,
        file_path=file_path,
        prompt_used="test prompt",
        cost_usd=0.08,
        created_at=datetime.now(timezone.utc),
        dalle_params={},
    )


async def test_compose_produces_valid_post(tmp_path: Path):
    from src.services.post_composer import PostComposerService

    settings = _make_settings(tmp_path)
    service = PostComposerService(settings=settings)
    template = _make_template()
    post_id = str(uuid.uuid4())

    raw_dir = tmp_path / "images" / post_id
    paths = [raw_dir / f"raw_{i}.jpg" for i in range(2)]
    images = []
    for p in paths:
        _create_fake_image(p)
        images.append(_make_generated_image(post_id, str(p)))

    composed = await service.compose(images, template, post_id)

    assert composed.id == post_id
    assert len(composed.composed_image_paths) == 2
    assert composed.caption.startswith("Texto principal")
    assert composed.total_cost_usd == pytest.approx(0.16)
    # PEND-04: sem gerador de IA, a origem da legenda é marcada como fallback
    assert composed.caption_source == "fallback"


def test_generate_caption_contains_template_text(tmp_path: Path):
    from src.services.post_composer import PostComposerService

    settings = _make_settings(tmp_path)
    service = PostComposerService(settings=settings)
    template = _make_template()

    caption = service.generate_caption(template)
    assert "Texto principal" in caption
    assert "#" in caption


def test_generate_caption_with_variables(tmp_path: Path):
    from src.services.post_composer import PostComposerService

    settings = _make_settings(tmp_path)
    service = PostComposerService(settings=settings)
    template = PromptTemplate(
        id="tpl2",
        name="T",
        prompt="p",
        variables={"mood": ["serene", "epic"]},
        caption_template="Feeling {mood} today.",
        hashtag_pool=[],
        image_count=1,
        dalle_params=DalleParams(),
    )

    caption = service.generate_caption(template)
    assert "{mood}" not in caption
    assert "Feeling" in caption


def test_caption_is_capped_at_instagram_limit():
    from src.services.post_composer import PostComposerService, INSTAGRAM_CAPTION_MAX_CHARS

    long_caption = ("palavra " * 500).strip()  # ~4000 chars
    capped = PostComposerService._enforce_caption_limit(long_caption)
    assert len(capped) <= INSTAGRAM_CAPTION_MAX_CHARS
    assert capped.endswith("palavra")  # corta na última palavra inteira

    short_caption = "legenda curta"
    assert PostComposerService._enforce_caption_limit(short_caption) == short_caption


async def test_caption_source_marks_ai_and_fallback(tmp_path: Path):
    """PEND-04: a origem da legenda (IA vs fallback) chega ao ComposedPost."""
    from unittest.mock import AsyncMock
    from src.services.post_composer import PostComposerService
    from src.services.caption_generator import CAPTION_SOURCE_AI, CAPTION_SOURCE_FALLBACK

    settings = _make_settings(tmp_path)
    template = _make_template()
    post_id = str(uuid.uuid4())
    raw = tmp_path / "images" / post_id / "raw_0.jpg"
    _create_fake_image(raw)
    images = [_make_generated_image(post_id, str(raw))]

    gen = MagicMock()
    gen.generate = AsyncMock(return_value=("legenda por IA", CAPTION_SOURCE_AI))
    service = PostComposerService(settings=settings, caption_generator=gen)
    composed = await service.compose(images, template, post_id)
    assert composed.caption_source == CAPTION_SOURCE_AI

    gen.generate = AsyncMock(return_value=("legenda do template", CAPTION_SOURCE_FALLBACK))
    composed = await service.compose(images, template, post_id)
    assert composed.caption_source == CAPTION_SOURCE_FALLBACK
