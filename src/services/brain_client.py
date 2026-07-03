"""Cliente do "cérebro" do agente — o LLM que pesquisa e redige texto.

Abstrai a chamada ao modelo de linguagem (Claude / Anthropic) que faz a
pesquisa de mercado (HU-BACKEND-02) e a redação de legenda (HU-BACKEND-03).
Mantém o resto do pipeline ignorante de qual SDK está por trás: as etapas de
negócio dependem da PORTA `BrainClient`, não da Anthropic.

A chave/modelo vêm do `Settings` (`ANTHROPIC_API_KEY`, `BRAIN_MODEL`), que já
existiam no config justamente para este papel.
"""
from ..config import Settings
from ..domain.ports import BrainClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_MAX_TOKENS = 1024


class AnthropicBrainClient:
    """Implementação do cérebro usando a API da Anthropic (Claude).

    O SDK (`anthropic`) é importado de forma preguiçosa para não tornar o
    pacote obrigatório quando o agente roda apenas o pipeline de imagem.
    """

    def __init__(self, settings: Settings):
        self._api_key = settings.anthropic_api_key
        self._model = settings.brain_model
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY não configurado — cérebro indisponível.")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - depende de dependência opcional
            raise RuntimeError(
                "Pacote 'anthropic' não instalado — rode `pip install anthropic`."
            ) from exc
        self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(self, system: str, prompt: str, max_tokens: int = _DEFAULT_MAX_TOKENS) -> str:
        client = self._ensure_client()
        message = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._extract_text(message)

    @staticmethod
    def _extract_text(message) -> str:
        parts = [block.text for block in getattr(message, "content", []) if getattr(block, "type", None) == "text"]
        text = "\n".join(parts).strip()
        if not text:
            raise RuntimeError("Cérebro não retornou texto.")
        return text


class OpenAIBrainClient:
    """Cérebro usando a API da OpenAI (Chat Completions)."""

    def __init__(self, settings: Settings):
        self._api_key = settings.openai_api_key
        self._model = settings.openai_brain_model
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY não configurado — cérebro indisponível.")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pacote 'openai' não instalado — rode `pip install openai`.") from exc
        self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def complete(self, system: str, prompt: str, max_tokens: int = _DEFAULT_MAX_TOKENS) -> str:
        client = self._ensure_client()
        message = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return self._extract_text(message)

    @staticmethod
    def _extract_text(message) -> str:
        choices = getattr(message, "choices", None) or []
        text = (choices[0].message.content if choices else "") or ""
        text = text.strip()
        if not text:
            raise RuntimeError("Cérebro não retornou texto.")
        return text


def build_brain_client(settings: Settings) -> BrainClient:
    """Fábrica do cérebro — seleciona o provider por `settings.brain_provider`."""
    provider = (settings.brain_provider or "openai").lower()
    client: BrainClient = AnthropicBrainClient(settings) if provider == "anthropic" else OpenAIBrainClient(settings)
    if not client.available:
        logger.warning(
            "Cérebro (%s) sem credencial — pesquisa/legenda/criação por IA cairão no fallback "
            "até a chave ser configurada.", provider,
        )
    return client
