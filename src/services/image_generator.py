import asyncio
import base64
import uuid

import httpx
from openai import AsyncOpenAI

from ..config import Settings
from ..domain.models.post import GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker, cost_per_image
from ..utils.logger import get_logger
from .base_image_generator import MAX_IMAGES, BaseImageGenerator

logger = get_logger(__name__)

_RATE_LIMIT_DELAY = 9.0
_GPT_IMAGE_SIZES = {"1024x1792": "1024x1536", "1792x1024": "1536x1024", "1024x1024": "1024x1024"}
_GPT_IMAGE_QUALITIES = {"hd": "high", "standard": "medium", "low": "low", "medium": "medium", "high": "high"}


class ImageGeneratorService(BaseImageGenerator):
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
        count = min(count or template.image_count, MAX_IMAGES)
        model = self._settings.dalle_model
        if model.startswith("gpt-image"):
            params = {
                "size": _GPT_IMAGE_SIZES.get(self._settings.dalle_default_size, "1024x1536"),
                "quality": _GPT_IMAGE_QUALITIES.get(self._settings.dalle_default_quality.lower(), "medium"),
            }
        else:
            p = template.dalle_params
            params = {"size": p.size, "quality": p.quality, "style": p.style, "response_format": "url"}

        unit_cost = cost_per_image(model, params["quality"])
        self._ensure_budget(unit_cost * count)

        images: list[GeneratedImage] = []
        for i in range(count):
            if i:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
            prompt = self._build_prompt(template, image_brief=image_brief, subject=subject)
            logger.info("Generating image %d/%d for post %s | prompt: %.80s...", i + 1, count, post_id, prompt)
            response = await self._client.images.generate(model=model, prompt=prompt, n=1, **params)
            data, ext = await self._image_bytes(response.data[0])
            file_path = self._save(data, post_id, i, ext)
            await self._budget.spend(unit_cost, post_id)
            images.append(GeneratedImage(
                id=str(uuid.uuid4()),
                post_id=post_id,
                file_path=str(file_path),
                prompt_used=prompt,
                cost_usd=unit_cost,
                dalle_params={"model": model, **params},
            ))

        self._warn_if_near_budget()
        return images

    def estimate_cost(self, count: int, quality: str | None = None) -> float:
        return cost_per_image(self._settings.dalle_model, quality or self._settings.dalle_default_quality) * count

    @staticmethod
    async def _image_bytes(item) -> tuple[bytes, str]:
        if item.url:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(item.url)
                response.raise_for_status()
            return response.content, "jpg"
        if item.b64_json:
            return base64.b64decode(item.b64_json), "png"
        raise RuntimeError("OpenAI não retornou imagem")
