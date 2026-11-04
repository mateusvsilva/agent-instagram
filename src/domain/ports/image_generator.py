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
