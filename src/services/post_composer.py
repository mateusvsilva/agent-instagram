import random
from pathlib import Path
from typing import Optional

from ..config import Settings
from ..domain.models.brand import BrandIdentity
from ..domain.models.content import MarketResearch
from ..domain.models.post import ComposedPost, GeneratedImage
from ..domain.models.template import PromptTemplate
from ..services.caption_generator import CaptionGeneratorService
from ..utils.image_processing import LogoOverlay, resize_for_instagram, validate_carousel
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Teto de caracteres de uma legenda no Instagram. Aplicado ANTES do preview,
# para que o operador aprove exatamente o texto que será publicado.
INSTAGRAM_CAPTION_MAX_CHARS = 2200


class PostComposerService:
    def __init__(self, settings: Settings, caption_generator: Optional[CaptionGeneratorService] = None):
        self._settings = settings
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

        composed_paths = await self._process_images(images, post_id)

        validation = validate_carousel(composed_paths)
        if not validation.valid:
            raise ValueError(f"Carousel validation failed: {validation.errors}")
        if validation.warnings:
            for w in validation.warnings:
                logger.warning("Carousel warning: %s", w)

        caption = await self._compose_caption(
            template=template,
            brand=brand,
            research=research,
            subject=subject,
            instruction=instruction,
        )
        caption = self._enforce_caption_limit(caption)
        total_cost = sum(img.cost_usd for img in images)

        return ComposedPost(
            id=post_id,
            template_id=template.id,
            images=images,
            composed_image_paths=[str(p) for p in composed_paths],
            caption=caption,
            hashtags=template.hashtag_pool,
            total_cost_usd=total_cost,
        )

    async def _compose_caption(
        self,
        *,
        template: PromptTemplate,
        brand: Optional[BrandIdentity],
        research: Optional[MarketResearch],
        subject: str,
        instruction: str,
    ) -> str:
        """Legenda por IA (HU-BACKEND-03) com fallback para a legenda do template.

        Quando não há gerador de IA injetado (compatibilidade) ou o cérebro está
        indisponível, mantém o comportamento legado de `caption_template`.
        """
        fallback = self.generate_caption(template)
        if self._caption_generator is None:
            return fallback

        post_subject = subject or template.name
        caption = await self._caption_generator.generate(
            subject=post_subject,
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
        truncated = caption[:INSTAGRAM_CAPTION_MAX_CHARS]
        return truncated.rsplit(None, 1)[0].strip()

    def generate_caption(self, template: PromptTemplate) -> str:
        """Legenda legada montada a partir do `caption_template` (fallback)."""
        caption = template.caption_template
        for var_name, choices in template.variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in caption and choices:
                caption = caption.replace(placeholder, random.choice(choices))

        hashtags = self._select_hashtags(template.hashtag_pool)
        if hashtags:
            caption = f"{caption}\n\n{' '.join(hashtags)}"

        return caption.strip()

    def _select_hashtags(self, pool: list[str], max_tags: int = 20) -> list[str]:
        if not pool:
            return []
        count = min(len(pool), max_tags)
        return random.sample(pool, count)

    async def _process_images(self, images: list[GeneratedImage], post_id: str) -> list[Path]:
        output_dir = self._images_dir / post_id / "composed"
        output_dir.mkdir(parents=True, exist_ok=True)
        composed: list[Path] = []
        logo = self._build_logo_overlay()

        for i, img in enumerate(images):
            raw_path = Path(img.file_path)
            out_path = output_dir / f"composed_{i}.jpg"
            composed_path = resize_for_instagram(raw_path, out_path, logo=logo)
            composed.append(composed_path)
            logger.debug("Composed image %d → %s", i, composed_path)

        return composed

    def _build_logo_overlay(self) -> Optional[LogoOverlay]:
        s = self._settings
        if not s.logo_enabled:
            return None
        return LogoOverlay(
            path=s.logo_path,
            position=s.logo_position,
            scale=s.logo_scale,
            margin=s.logo_margin,
            opacity=s.logo_opacity,
        )
