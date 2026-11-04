from typing import Protocol, runtime_checkable


@runtime_checkable
class BrainClient(Protocol):
    available: bool

    async def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str: ...
