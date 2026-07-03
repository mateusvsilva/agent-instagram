import asyncio
import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from ..config import Settings
from ..domain.models.post import GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker, cost_per_image
from ..utils.logger import get_logger
from .base_image_generator import BaseImageGenerator

logger = get_logger(__name__)

_DALL_E_RATE_LIMIT_DELAY = 9.0  # ~7 images/min => 1 per ~8.5s, using 9s to be safe


class ImageGeneratorService(BaseImageGenerator):
    # DALL-E recebia os labels em inglês — preservado.
    _BRAND_BRIEF_LABEL = "Brand guidelines to respect:"
    _SUBJECT_LABEL = "Post subject:"

    def __init__(self, settings: Settings, budget_tracker: BudgetTracker):
        super().__init__(settings, budget_tracker)
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        template: PromptTemplate,
        post_id: str,
        count: int | None = None,
        image_brief: str = "",
        subject: str = "",
    ) -> list[GeneratedImage]:
        count = count or template.image_count
        if count > 10:
            count = 10

        params = template.dalle_params
        model = self._settings.dalle_model
        is_gpt_image = model.startswith("gpt-image")

        if is_gpt_image:
            # gpt-image-1: a API difere do DALL-E (base64, sem style/response_format,
            # quality low/medium/high). O .env (DALLE_*) é a fonte de verdade aqui.
            size = self._gpt_image_size(self._settings.dalle_default_size)
            quality = self._gpt_image_quality(self._settings.dalle_default_quality)
            style = None
        else:
            size = params.size
            quality = params.quality
            style = params.style

        unit_cost = cost_per_image(model, quality)
        self._ensure_budget(unit_cost * count)

        images: list[GeneratedImage] = []
        for i in range(count):
            prompt = self._build_prompt(template, image_brief=image_brief, subject=subject)
            logger.info("Generating image %d/%d for post %s | prompt: %.80s...", i + 1, count, post_id, prompt)

            if is_gpt_image:
                response = await self._client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1,
                )
                b64 = response.data[0].b64_json
                if not b64:
                    raise RuntimeError(f"gpt-image-1 returned no image data for image {i + 1}")
                file_path = self._save_b64(b64, post_id, i)
            else:
                response = await self._client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    style=style,
                    n=1,
                    response_format="url",
                )
                image_url = response.data[0].url
                if not image_url:
                    raise RuntimeError(f"DALL-E returned no URL for image {i + 1}")
                file_path = await self._download_image(image_url, post_id, i)

            self._budget.record(unit_cost)

            images.append(
                GeneratedImage(
                    id=str(uuid.uuid4()),
                    post_id=post_id,
                    file_path=str(file_path),
                    prompt_used=prompt,
                    cost_usd=unit_cost,
                    created_at=datetime.now(timezone.utc),
                    dalle_params={
                        "model": model,
                        "size": size,
                        "quality": quality,
                        "style": style,
                    },
                )
            )

            if i < count - 1:
                await asyncio.sleep(_DALL_E_RATE_LIMIT_DELAY)

        self._warn_if_near_budget()

        return images

    def estimate_cost(self, count: int, quality: str | None = None) -> float:
        q = quality or self._settings.dalle_default_quality
        return cost_per_image(self._settings.dalle_model, q) * count

    @staticmethod
    def _gpt_image_size(size: str) -> str:
        """Mapeia tamanhos do DALL-E para os aceitos pelo gpt-image-1."""
        mapping = {
            "1024x1792": "1024x1536",  # retrato
            "1792x1024": "1536x1024",  # paisagem
            "1024x1024": "1024x1024",  # quadrado
        }
        return mapping.get(size, "1024x1536")

    @staticmethod
    def _gpt_image_quality(quality: str) -> str:
        """Mapeia quality do DALL-E (hd/standard) para gpt-image-1 (low/medium/high)."""
        q = (quality or "").lower()
        if q in ("low", "medium", "high"):
            return q
        return {"hd": "high", "standard": "medium"}.get(q, "medium")

    def _save_b64(self, b64: str, post_id: str, index: int) -> Path:
        save_dir = self._images_dir / post_id
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"raw_{index}.png"
        file_path.write_bytes(base64.b64decode(b64))
        logger.debug("Saved gpt-image %d to %s", index, file_path)
        return file_path

    async def _download_image(self, url: str, post_id: str, index: int) -> Path:
        save_dir = self._images_dir / post_id
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"raw_{index}.jpg"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            file_path.write_bytes(response.content)

        logger.debug("Saved image %d to %s", index, file_path)
        return file_path
