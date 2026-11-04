from openai import AsyncOpenAI

from ..config import Settings
from ..domain.ports import BrainClient
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _require_text(text: str | None) -> str:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Cérebro não retornou texto.")
    return text


class AnthropicBrainClient:
    def __init__(self, settings: Settings):
        self._api_key = settings.anthropic_api_key
        self._model = settings.brain_model
        self.available = bool(self._api_key)
        self._client = None

    async def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        if not self.available:
            raise RuntimeError("ANTHROPIC_API_KEY não configurado — cérebro indisponível.")
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return _require_text("\n".join(b.text for b in message.content if b.type == "text"))


class OpenAIBrainClient:
    def __init__(self, settings: Settings):
        self._model = settings.openai_brain_model
        self.available = bool(settings.openai_api_key)
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if self.available else None

    async def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        if self._client is None:
            raise RuntimeError("OPENAI_API_KEY não configurado — cérebro indisponível.")
        message = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return _require_text(message.choices[0].message.content if message.choices else "")


def build_brain_client(settings: Settings) -> BrainClient:
    client_cls = AnthropicBrainClient if settings.brain_provider == "anthropic" else OpenAIBrainClient
    client = client_cls(settings)
    if not client.available:
        logger.warning(
            "Cérebro (%s) sem credencial — pesquisa/legenda/criação por IA cairão no fallback.",
            settings.brain_provider,
        )
    return client
