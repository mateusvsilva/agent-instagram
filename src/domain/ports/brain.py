"""Porta `BrainClient` — o "cérebro" (LLM) que pesquisa e redige texto.

Abstrai a chamada ao modelo de linguagem (hoje Claude/Anthropic) usado pela
pesquisa de mercado e pela geração de legenda. Implementada hoje por
`AnthropicBrainClient`. O resto do pipeline depende desta porta, não do SDK.
"""
from typing import Protocol, runtime_checkable

_DEFAULT_MAX_TOKENS = 1024


@runtime_checkable
class BrainClient(Protocol):
    """Recebe uma instrução e devolve texto livre do modelo."""

    async def complete(
        self,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str: ...

    @property
    def available(self) -> bool:
        """True quando há credencial/SDK para chamar o modelo de verdade."""
        ...
