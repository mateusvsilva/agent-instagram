"""Popula o banco do agente com dados de demonstracao para o Hub.

Uso:
    python -m scripts.seed_demo

Gera posts com status variados nos ultimos 14 dias, incluindo imagens
JPEG reais em data/images/, para visualizar o painel populado.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from src.config import get_settings
from src.domain.models.enums import ApprovalStatus, PostStatus
from src.domain.models.post import GeneratedImage, Post
from src.services.storage import StorageService

PROMPTS = [
    "A breathtaking realistic landscape at sunset, warm golden color palette, serene atmosphere",
    "A breathtaking watercolor landscape at sunset, deep crimson color palette, dramatic atmosphere",
    "Minimalist product photography of artisan coffee, soft morning light, editorial style",
    "Urban architecture at blue hour, neon reflections, cinematic mood",
]

CAPTIONS = [
    "Momentos que inspiram.",
    "A beleza está nos detalhes.",
    "Cada dia uma nova perspectiva.",
    "Arte gerada, emoção real.",
]

PALETTES = [
    ((255, 94, 58), (40, 10, 60)),
    ((76, 201, 240), (10, 20, 50)),
    ((61, 220, 151), (5, 40, 35)),
    ((255, 179, 71), (60, 25, 5)),
]


def make_image(path: Path) -> None:
    top, bottom = random.choice(PALETTES)
    img = Image.new("RGB", (540, 675))
    for y in range(675):
        t = y / 675
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(540):
            img.putpixel((x, y), color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=80)


async def main() -> None:
    settings = get_settings()
    storage = StorageService(settings.db_path)
    await storage.initialize()

    now = datetime.now(timezone.utc)
    outcomes = (
        [("published", "published")] * 6
        + [("failed", "rejected")] * 2
        + [("awaiting_approval", "pending")] * 2
        + [("discarded", "expired")]
        + [("failed", "failed")]
    )
    random.shuffle(outcomes)

    for index, (status, approval) in enumerate(outcomes):
        post_id = uuid.uuid4().hex[:12]
        created = now - timedelta(days=random.uniform(0, 14))
        image_count = random.choice([2, 3, 4])
        images = []
        for n in range(image_count):
            image_id = uuid.uuid4().hex[:12]
            file_path = settings.images_dir / post_id / f"{n}.jpg"
            make_image(file_path)
            images.append(
                GeneratedImage(
                    id=image_id,
                    post_id=post_id,
                    file_path=str(file_path),
                    prompt_used=random.choice(PROMPTS),
                    cost_usd=0.08,
                    created_at=created,
                    dalle_params={"size": "1024x1792", "quality": "hd", "style": "vivid"},
                )
            )

        post = Post(
            id=post_id,
            template_id=random.choice(["sunset_landscape", "coffee_editorial", "urban_night"]),
            caption=random.choice(CAPTIONS),
            hashtags=["#aiart", "#impressam", "#generative"],
            status=PostStatus(status),
            approval_status=ApprovalStatus(approval),
            total_cost_usd=round(0.08 * image_count, 2),
            images=images,
            created_at=created,
            published_at=created + timedelta(hours=2) if status == "published" else None,
            error="Instagram challenge required" if approval == "failed" else None,
        )
        await storage.save_post(post)
        if approval == "failed":
            await storage.save_error(post_id, "Instagram challenge required: verificação manual necessária")

    print(f"Seed concluído: {len(outcomes)} posts de demonstração criados em {settings.db_path}")


if __name__ == "__main__":
    asyncio.run(main())
