import random
from pathlib import Path
from typing import Optional

from ..config import Settings
from ..domain.models.brand import BrandIdentity
from ..domain.models.content import MarketResearch
from ..domain.models.post import ComposedPost, GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.image_processing import resize_for_instagram, validate_carousel
from ..utils.logger import get_logger
from .caption_generator import CaptionGeneratorService

logger = get_logger(__name__)

INSTAGRAM_CAPTION_MAX_CHARS = 2200
MAX_HASHTAGS = 20


class PostComposerService:
    def __init__(self, settings: Settings, caption_generator: Optional[CaptionGeneratorService] = None):
        self._images_dir = settings.images_dir
        self._caption_generator = caption_generator

    async def compose(
        self,
        images: list[GeneratedImage],
        template: PromptTemplate,
        post_id: str,
        *,
        brand: Optional[BrandIdentity] = None,
        research: Optional[MarketResearch] = None,
        subject: str = "",
        instruction: str = "",
    ) -> ComposedPost:
        logger.info("Composing post %s with %d images", post_id, len(images))
        composed_paths = self._process_images(images, post_id)

        validation = validate_carousel(composed_paths)
        if not validation.valid:
            raise ValueError(f"Carousel validation failed: {validation.errors}")
        for warning in validation.warnings:
            logger.warning("Carousel warning: %s", warning)

        caption = await self._compose_caption(template, brand, research, subject, instruction)
        return ComposedPost(
            id=post_id,
            template_id=template.id,
            images=images,
            composed_image_paths=[str(p) for p in composed_paths],
            caption=self._enforce_caption_limit(caption),
            hashtags=template.hashtag_pool,
            total_cost_usd=sum(img.cost_usd for img in images),
        )

    async def _compose_caption(
        self,
        template: PromptTemplate,
        brand: Optional[BrandIdentity],
        research: Optional[MarketResearch],
        subject: str,
        instruction: str,
    ) -> str:
        fallback = self.generate_caption(template)
        if self._caption_generator is None:
            return fallback
        caption = await self._caption_generator.generate(
            subject=subject or template.name,
            brand=brand or BrandIdentity(),
            research=research,
            template=template,
            instruction=instruction,
            fallback_caption=fallback,
        )
        return caption or fallback

    @staticmethod
    def _enforce_caption_limit(caption: str) -> str:
        if len(caption) <= INSTAGRAM_CAPTION_MAX_CHARS:
            return caption
        logger.warning(
            "Legenda excedeu o teto do Instagram (%d > %d chars) — truncando na última palavra.",
            len(caption), INSTAGRAM_CAPTION_MAX_CHARS,
        )
        return caption[:INSTAGRAM_CAPTION_MAX_CHARS].rsplit(None, 1)[0].strip()

    @staticmethod
    def generate_caption(template: PromptTemplate) -> str:
        caption = template.caption_template
        for var_name, choices in template.variables.items():
            if choices:
                caption = caption.replace(f"{{{var_name}}}", random.choice(choices))
        pool = template.hashtag_pool
        if pool:
            caption = f"{caption}\n\n{' '.join(random.sample(pool, min(len(pool), MAX_HASHTAGS)))}"
        return caption.strip()

    def _process_images(self, images: list[GeneratedImage], post_id: str) -> list[Path]:
        output_dir = self._images_dir / post_id / "composed"
        return [
            resize_for_instagram(Path(img.file_path), output_dir / f"composed_{i}.jpg")
            for i, img in enumerate(images)
        ]
