from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageUploader(Protocol):
    async def upload(self, path: str) -> str: ...
