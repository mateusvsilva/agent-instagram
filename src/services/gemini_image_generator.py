import asyncio
import uuid

from ..config import Settings
from ..domain.models.post import GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker
from ..utils.logger import get_logger
from .base_image_generator import MAX_IMAGES, BaseImageGenerator

logger = get_logger(__name__)

_RATE_LIMIT_DELAY = 2.0


class GeminiImageGeneratorService(BaseImageGenerator):
    def __init__(self, settings: Settings, budget_tracker: BudgetTracker):
        from google import genai
        from google.genai import types

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY não configurado no .env")
        super().__init__(settings, budget_tracker)
        self._model = settings.gemini_model
        self._aspect_ratio = settings.gemini_aspect_ratio
        self._unit_cost = settings.gemini_cost_per_image
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=self._aspect_ratio) if self._aspect_ratio else None,
        )

    async def generate(
        self,
        template: PromptTemplate,
        post_id: str,
        count: int | None = None,
        image_brief: str = "",
        subject: str = "",
    ) -> list[GeneratedImage]:
        count = min(count or template.image_count, MAX_IMAGES)
        self._ensure_budget(self._unit_cost * count)

        images: list[GeneratedImage] = []
        for i in range(count):
            if i:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
            prompt = self._build_prompt(template, image_brief=image_brief, subject=subject)
            logger.info("Gemini gerando imagem %d/%d (post %s) | prompt: %.80s...", i + 1, count, post_id, prompt)
            data = await asyncio.to_thread(self._generate_one, prompt)
            file_path = self._save(data, post_id, i, "png")
            self._budget.record(self._unit_cost)
            images.append(GeneratedImage(
                id=str(uuid.uuid4()),
                post_id=post_id,
                file_path=str(file_path),
                prompt_used=prompt,
                cost_usd=self._unit_cost,
                dalle_params={"model": self._model, "aspect_ratio": self._aspect_ratio},
            ))

        self._warn_if_near_budget()
        return images

    def estimate_cost(self, count: int, quality: str | None = None) -> float:
        return self._unit_cost * count

    def _generate_one(self, prompt: str) -> bytes:
        response = self._client.models.generate_content(model=self._model, contents=prompt, config=self._config)
        for part in response.parts or []:
            if part.inline_data is not None and part.inline_data.data:
                return part.inline_data.data
        raise RuntimeError("Gemini não retornou imagem (verifique o prompt / política de conteúdo)")
