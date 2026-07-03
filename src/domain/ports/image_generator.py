"""Porta `ImageGenerator` — contrato dos geradores de imagem.

Implementado hoje por `GeminiImageGeneratorService` (Google Gemini) e
`ImageGeneratorService` (DALL-E / gpt-image-1). Ambos compartilham esta mesma
assinatura por convenção; a porta a torna explícita.
"""
from typing import Protocol, runtime_checkable

from ..models.post import GeneratedImage
from ..models.template import PromptTemplate


@runtime_checkable
class ImageGenerator(Protocol):
    async def generate(
        self,
        template: PromptTemplate,
        post_id: str,
        count: int | None = None,
        image_brief: str = "",
        subject: str = "",
    ) -> list[GeneratedImage]: ...

    def estimate_cost(self, count: int, quality: str | None = None) -> float: ...
