"""Gera imagens com o Google Gemini (modelos "Nano Banana").

Substituto direto do ImageGeneratorService (DALL-E): mesma assinatura
`generate(template, post_id, count)` devolvendo list[GeneratedImage], salvando
os arquivos locais em images_dir/<post_id>/raw_<i>.png.

SDK: google-genai (sync) — chamadas embrulhadas em asyncio.to_thread.
Chave: https://aistudio.google.com/apikey  (env GEMINI_API_KEY).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..domain.models.post import GeneratedImage
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker
from ..utils.logger import get_logger
from .base_image_generator import BaseImageGenerator

logger = get_logger(__name__)

_RATE_LIMIT_DELAY = 2.0  # pequeno respiro entre imagens


class GeminiImageGeneratorService(BaseImageGenerator):
    def __init__(self, settings: Settings, budget_tracker: BudgetTracker):
        from google import genai

        super().__init__(settings, budget_tracker)
        self._model = settings.gemini_model
        self._aspect_ratio = settings.gemini_aspect_ratio
        self._unit_cost = settings.gemini_cost_per_image
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY não configurado no .env")
        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def generate(
        self,
        template: PromptTemplate,
        post_id: str,
        count: int | None = None,
        image_brief: str = "",
        subject: str = "",
    ) -> list[GeneratedImage]:
        """Gera imagens.

        `image_brief` (HU-BACKEND-05) traz as diretrizes de marca (identity +
        image_guidelines) e `subject` (HU-BACKEND-01/02) o assunto pedido —
        ambos opcionais para manter retrocompatibilidade com `/force` e scripts.
        """
        count = count or template.image_count
        count = min(count, 10)

        self._ensure_budget(self._unit_cost * count)

        images: list[GeneratedImage] = []
        for i in range(count):
            prompt = self._build_prompt(template, image_brief=image_brief, subject=subject)
            logger.info("Gemini gerando imagem %d/%d (post %s) | prompt: %.80s...", i + 1, count, post_id, prompt)

            image_bytes = await asyncio.to_thread(self._generate_one, prompt)
            file_path = self._save_image(image_bytes, post_id, i)
            self._budget.record(self._unit_cost)

            images.append(
                GeneratedImage(
                    id=str(uuid.uuid4()),
                    post_id=post_id,
                    file_path=str(file_path),
                    prompt_used=prompt,
                    cost_usd=self._unit_cost,
                    created_at=datetime.now(timezone.utc),
                    dalle_params={"model": self._model, "aspect_ratio": self._aspect_ratio},
                )
            )

            if i < count - 1:
                await asyncio.sleep(_RATE_LIMIT_DELAY)

        self._warn_if_near_budget()

        return images

    def estimate_cost(self, count: int, quality: str | None = None) -> float:
        return self._unit_cost * count

    def _generate_one(self, prompt: str) -> bytes:
        from google.genai import types

        config = None
        if self._aspect_ratio:
            try:
                config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=self._aspect_ratio),
                )
            except Exception:  # SDK mais antigo sem image_config
                config = None

        try:
            response = self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )
        except TypeError:
            response = self._client.models.generate_content(model=self._model, contents=prompt)

        for part in response.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data
            if getattr(part, "text", None):
                logger.debug("Gemini texto: %.120s", part.text)

        raise RuntimeError("Gemini não retornou imagem (verifique o prompt / política de conteúdo)")

    def _save_image(self, data: bytes, post_id: str, index: int) -> Path:
        save_dir = self._images_dir / post_id
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"raw_{index}.png"
        file_path.write_bytes(data)
        logger.debug("Imagem Gemini salva em %s (%d bytes)", file_path, len(data))
        return file_path
