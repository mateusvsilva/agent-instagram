import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.models.enums import ApprovalStatus, PostStatus
from src.domain.models.post import GeneratedImage, Post
from src.services.storage import StorageService


@pytest.fixture
async def storage(tmp_path: Path) -> StorageService:
    svc = StorageService(db_path=tmp_path / "test.db")
    await svc.initialize()
    return svc


def _make_post(**kwargs) -> Post:
    return Post(
        id=str(uuid.uuid4()),
        template_id="test_template",
        **kwargs,
    )


async def test_save_and_retrieve_post(storage: StorageService):
    post = _make_post()
    await storage.save_post(post)
    retrieved = await storage.get_post(post.id)
    assert retrieved is not None
    assert retrieved.id == post.id
    assert retrieved.template_id == "test_template"


async def test_update_status(storage: StorageService):
    post = _make_post()
    await storage.save_post(post)
    await storage.update_status(post.id, status=PostStatus.PUBLISHED, approval_status=ApprovalStatus.APPROVED)
    updated = await storage.get_post(post.id)
    assert updated.status == PostStatus.PUBLISHED
    assert updated.approval_status == ApprovalStatus.APPROVED


async def test_get_history_returns_ordered(storage: StorageService):
    for _ in range(3):
        await storage.save_post(_make_post())
    history = await storage.get_history(limit=10)
    assert len(history) == 3
    timestamps = [p.created_at for p in history]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_get_pending_posts(storage: StorageService):
    pending = _make_post()
    published = _make_post(approval_status=ApprovalStatus.APPROVED, status=PostStatus.PUBLISHED)
    await storage.save_post(pending)
    await storage.save_post(published)
    result = await storage.get_pending_posts()
    ids = [p.id for p in result]
    assert pending.id in ids
    assert published.id not in ids


async def test_metrics(storage: StorageService):
    for i in range(5):
        status = PostStatus.PUBLISHED if i < 3 else PostStatus.DISCARDED
        approval = ApprovalStatus.APPROVED if i < 3 else ApprovalStatus.REJECTED
        await storage.save_post(_make_post(status=status, approval_status=approval, total_cost_usd=0.08))
    metrics = await storage.get_metrics("30d")
    assert metrics.total_posts == 5
    assert metrics.published == 3
    assert metrics.rejected == 2
    assert abs(metrics.total_cost_usd - 0.40) < 0.001


async def test_save_error(storage: StorageService):
    post = _make_post()
    await storage.save_post(post)
    await storage.save_error(post.id, "something went wrong")
    updated = await storage.get_post(post.id)
    assert "something went wrong" in updated.error


async def test_post_with_images(storage: StorageService):
    post = _make_post()
    post.images = [
        GeneratedImage(
            id=str(uuid.uuid4()),
            post_id=post.id,
            file_path="/tmp/img.jpg",
            prompt_used="test prompt",
            cost_usd=0.08,
            created_at=datetime.now(timezone.utc),
            dalle_params={"model": "dall-e-3"},
        )
    ]
    await storage.save_post(post)
    retrieved = await storage.get_post(post.id)
    assert len(retrieved.images) == 1
    assert retrieved.images[0].prompt_used == "test prompt"
