# Fluxo Conversacional de Criação de Imagem — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para implementar tarefa a tarefa. Passos usam checkbox (`- [ ]`).
> **Nota deste ambiente:** essas sub-skills NÃO estão instaladas e **o diretório não é repositório git**. Portanto: (a) execução inline pelo próprio agente; (b) **sem passos de `git commit`** — o checkpoint de cada tarefa é rodar a suíte (`python -m pytest -q`). Os passos abaixo usam TDD (teste falha → implementa → teste passa → suíte verde).

**Goal:** Adicionar um comando `/criar` no Telegram que conduz uma conversa para gerar UMA imagem por vez (IA interpreta o brief e o feedback), e ao aprovar compõe a legenda no tom da marca e publica via Buffer — reusando a publicação existente.

**Architecture:** Sessão de criação dedicada (`CreationService` + `CreationSession`) que conversa via cérebro de texto (`ArtDirectorService` sobre a porta `BrainClient`, provider configurável OpenAI/Anthropic), gera 1 imagem por rodada reusando `image_generator.generate()` com um `PromptTemplate` ad-hoc, e ao final entrega um `ComposedPost` de imagem única para `_publish_composed` (reusa `_publish`/Buffer). O `_run_pipeline` atual fica intacto.

**Tech Stack:** Python 3.11, pydantic/pydantic-settings, python-telegram-bot ≥21.3, openai ≥1.30, pytest + pytest-asyncio (`asyncio_mode=auto`), pytest-mock, PIL.

## Global Constraints

- Idioma: diretrizes/legendas em pt-BR; o **prompt de imagem** (campo `prompt`) em inglês.
- Banner = texto curto **CAIXA ALTA sem acento** dentro da imagem.
- A porta `BrainClient` **não muda**: `async complete(system, prompt, max_tokens=1024) -> str`, `available: bool`.
- A porta `ImageGenerator` **não muda**: `async generate(template, post_id, count=None, image_brief="", subject="") -> list[GeneratedImage]`.
- Pesquisa de mercado é **pulada** no modo conversacional.
- Post de **imagem única** (MVP); `validate_carousel` já aceita 1 imagem.
- Orçamento: checar `budget.can_spend` antes de gerar; cap suave `CREATION_MAX_ROUNDS`.
- Sem regressão em `/force` e "poste sobre X".
- Testes **não chamam API real** (cérebro e gerador de imagem sempre fakes nos testes).
- Imports de teste no padrão `from src...`; rodar a partir da raiz do repo.

## File Structure

- **Create** `src/services/art_director.py` — monta/revisa o prompt de imagem via cérebro.
- **Create** `src/domain/models/creation.py` — `CreationState`, `CreationMode`, `CreationSession`.
- **Create** `src/services/creation_service.py` — máquina de estados da sessão de criação.
- **Create** `src/handlers/creation_handler.py` — callbacks dos botões + builders de teclado.
- **Modify** `src/services/brain_client.py` — `OpenAIBrainClient` + `build_brain_client` por provider.
- **Modify** `src/config.py` — `BRAIN_PROVIDER`, `OPENAI_BRAIN_MODEL`, `CREATION_SESSION_TIMEOUT`, `CREATION_MAX_ROUNDS`.
- **Modify** `src/handlers/conversation_handler.py` — rotear texto para a sessão ativa.
- **Modify** `src/handlers/command_handler.py` — `cmd_criar`.
- **Modify** `src/services/telegram_bot.py` — registrar `/criar`, callbacks `create:*`, previews.
- **Modify** `src/main.py` — wiring + `_publish_composed`.
- **Modify** `.env.example` — documentar as novas envs.
- **Tests** `tests/test_brain_client.py`, `tests/test_art_director.py`, `tests/test_creation_service.py`, `tests/test_creation_handler.py`, `tests/test_conversation_routing.py`.

---

### Task 1: Cérebro OpenAI + fábrica por provider

**Files:**
- Modify: `src/config.py`
- Modify: `src/services/brain_client.py`
- Modify: `.env.example`
- Test: `tests/test_brain_client.py`

**Interfaces:**
- Consumes: porta `BrainClient` (`available`, `async complete(system, prompt, max_tokens=1024) -> str`).
- Produces: `OpenAIBrainClient(settings)`; `build_brain_client(settings) -> BrainClient` selecionando por `settings.brain_provider`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_brain_client.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.brain_client import OpenAIBrainClient, AnthropicBrainClient, build_brain_client


def _settings(**over):
    s = MagicMock()
    s.openai_api_key = over.get("openai_api_key", "sk-test")
    s.openai_brain_model = "gpt-4o-mini"
    s.anthropic_api_key = over.get("anthropic_api_key", "")
    s.brain_model = "claude-x"
    s.brain_provider = over.get("brain_provider", "openai")
    return s


def test_openai_available_reflects_key():
    assert OpenAIBrainClient(_settings()).available is True
    assert OpenAIBrainClient(_settings(openai_api_key="")).available is False


def test_factory_selects_provider():
    assert isinstance(build_brain_client(_settings(brain_provider="openai")), OpenAIBrainClient)
    assert isinstance(build_brain_client(_settings(brain_provider="anthropic")), AnthropicBrainClient)


async def test_openai_complete_extracts_text(monkeypatch):
    fake_msg = MagicMock()
    fake_msg.choices = [MagicMock(message=MagicMock(content="  hello  "))]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_msg)
    brain = OpenAIBrainClient(_settings())
    monkeypatch.setattr(brain, "_ensure_client", lambda: fake_client)
    out = await brain.complete("sys", "user", max_tokens=50)
    assert out == "hello"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_brain_client.py -q`
Expected: FAIL (`ImportError: cannot import name 'OpenAIBrainClient'`).

- [ ] **Step 3: Adicionar os campos de config**

Em `src/config.py`, logo após o bloco do `brain_model` (linha ~26), adicionar:

```python
    # Cérebro de texto configurável: "openai" ou "anthropic"
    brain_provider: str = Field("openai", alias="BRAIN_PROVIDER")
    openai_brain_model: str = Field("gpt-4o-mini", alias="OPENAI_BRAIN_MODEL")
```

- [ ] **Step 4: Implementar `OpenAIBrainClient` e a fábrica**

Em `src/services/brain_client.py`, adicionar a classe e substituir `build_brain_client`:

```python
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
```

- [ ] **Step 5: Documentar no `.env.example`**

Adicionar:
```
# Cérebro de texto: "openai" (reusa OPENAI_API_KEY) ou "anthropic"
BRAIN_PROVIDER=openai
OPENAI_BRAIN_MODEL=gpt-4o-mini
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_brain_client.py -q`
Expected: PASS (3 passed).

---

### Task 2: ArtDirectorService (monta/revisa o prompt de imagem)

**Files:**
- Create: `src/services/art_director.py`
- Test: `tests/test_art_director.py`

**Interfaces:**
- Consumes: `BrainClient`, `BrandIdentity.image_brief() -> str`.
- Produces: `ArtDirectorService(brain, brand, max_tokens=400)` com `async build_image_prompt(brief: str, mode: str="auto") -> str` e `async revise_image_prompt(current_prompt: str, feedback: str) -> str`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_art_director.py
from unittest.mock import AsyncMock, MagicMock
from src.services.art_director import ArtDirectorService


def _brand():
    b = MagicMock()
    b.image_brief.return_value = "DIRETRIZES: editorial, aço, azul #1B4D7E"
    return b


async def test_build_prompt_includes_brand_and_returns_text():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="  macro shot of a gear  ")
    art = ArtDirectorService(brain=brain, brand=_brand())
    out = await art.build_image_prompt("uma engrenagem", mode="clean")
    assert out == "macro shot of a gear"
    sys_arg, user_arg = brain.complete.call_args.args[0], brain.complete.call_args.args[1]
    assert "DIRETRIZES" in user_arg and "engrenagem" in user_arg


async def test_banner_mode_instructs_uppercase_no_accent():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="banner")
    art = ArtDirectorService(brain=brain, brand=_brand())
    await art.build_image_prompt("quando vale 3D", mode="banner")
    system = brain.complete.call_args.args[0]
    assert "CAIXA ALTA" in system and "ACENTO" in system.upper()


async def test_revise_passes_current_and_feedback():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="darker gear")
    art = ArtDirectorService(brain=brain, brand=_brand())
    out = await art.revise_image_prompt("a gear", "mais escuro")
    assert out == "darker gear"
    user = brain.complete.call_args.args[1]
    assert "a gear" in user and "mais escuro" in user
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_art_director.py -q`
Expected: FAIL (`ModuleNotFoundError: src.services.art_director`).

- [ ] **Step 3: Implementar o serviço**

```python
# src/services/art_director.py
"""Diretor de arte: traduz o brief/feedback do operador em prompt de imagem.

Usa a porta BrainClient (cérebro de texto) + as diretrizes de marca (image_brief).
Não chama o modelo de imagem — só produz o texto do prompt.
"""
from ..domain.models.brand import BrandIdentity
from ..domain.ports import BrainClient

_SYSTEM_BUILD = (
    "Você é diretor de arte de uma marca de impressão 3D industrial. Com base nas "
    "diretrizes de marca e no pedido do operador, escreva UM prompt de geração de "
    "imagem em INGLÊS, conciso, seguindo as diretrizes. Se o formato for banner, "
    "inclua um texto curto em CAIXA ALTA SEM ACENTO dentro da imagem. "
    "Responda APENAS com o prompt, sem aspas e sem explicação."
)
_SYSTEM_REVISE = (
    "Você é diretor de arte de uma marca de impressão 3D industrial. Receberá um "
    "prompt de imagem atual (em inglês) e um ajuste pedido pelo operador (em "
    "português). Devolva o prompt REVISADO em INGLÊS, incorporando o ajuste e "
    "mantendo o estilo da marca. Responda APENAS com o prompt."
)
_MODE_LABELS = {
    "clean": "foto limpa do produto, sem texto na imagem",
    "banner": "banner com texto curto sobre a imagem",
    "auto": "decida o melhor formato (foto limpa ou banner)",
}


class ArtDirectorService:
    def __init__(self, brain: BrainClient, brand: BrandIdentity, max_tokens: int = 400):
        self._brain = brain
        self._brand = brand
        self._max_tokens = max_tokens

    async def build_image_prompt(self, brief: str, mode: str = "auto") -> str:
        user = self._compose_build_user(brief, mode)
        out = await self._brain.complete(_SYSTEM_BUILD, user, max_tokens=self._max_tokens)
        return out.strip()

    async def revise_image_prompt(self, current_prompt: str, feedback: str) -> str:
        user = f"PROMPT ATUAL:\n{current_prompt}\n\nAJUSTE PEDIDO:\n{feedback}"
        out = await self._brain.complete(_SYSTEM_REVISE, user, max_tokens=self._max_tokens)
        return out.strip()

    def _compose_build_user(self, brief: str, mode: str) -> str:
        parts: list[str] = []
        brief_marca = self._brand.image_brief()
        if brief_marca.strip():
            parts.append("=== DIRETRIZES DE MARCA ===\n" + brief_marca.strip())
        parts.append("=== FORMATO ===\n" + _MODE_LABELS.get(mode, _MODE_LABELS["auto"]))
        parts.append("=== PEDIDO DO OPERADOR ===\n" + brief.strip())
        return "\n\n".join(parts)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_art_director.py -q`
Expected: PASS (3 passed).

---

### Task 3: Modelo de sessão + esqueleto do CreationService

**Files:**
- Create: `src/domain/models/creation.py`
- Create: `src/services/creation_service.py`
- Modify: `src/config.py`
- Test: `tests/test_creation_service.py`

**Interfaces:**
- Consumes: `BrainClient.available`; telegram fake com `async notify(text)`.
- Produces:
  - `CreationState`, `CreationMode`, `CreationSession` (em `creation.py`).
  - `CreationService(*, brain, art_director, image_generator, brand, budget, post_composer, telegram, settings)` com atributo público `on_complete` e métodos `async start(chat_id)`, `async cancel(chat_id)`, `has_active_session(chat_id) -> bool`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_creation_service.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.creation_service import CreationService
from src.domain.models.creation import CreationState


def _telegram():
    t = MagicMock()
    t.notify = AsyncMock(return_value="1")
    t.send_mode_prompt = AsyncMock()
    t.send_creation_preview = AsyncMock()
    t.send_creation_final_preview = AsyncMock()
    return t


def _settings():
    s = MagicMock()
    s.creation_max_rounds = 12
    s.creation_session_timeout = 1800
    return s


def make_service(brain_available=True, telegram=None, **over):
    brain = MagicMock(); brain.available = brain_available
    svc = CreationService(
        brain=brain,
        art_director=over.get("art_director", MagicMock()),
        image_generator=over.get("image_generator", MagicMock()),
        brand=over.get("brand", MagicMock()),
        budget=over.get("budget", MagicMock()),
        post_composer=over.get("post_composer", MagicMock()),
        telegram=telegram or _telegram(),
        settings=_settings(),
    )
    return svc


async def test_start_blocks_without_brain():
    t = _telegram()
    svc = make_service(brain_available=False, telegram=t)
    await svc.start(123)
    assert svc.has_active_session(123) is False
    t.notify.assert_awaited()


async def test_start_creates_session_and_greets():
    t = _telegram()
    svc = make_service(telegram=t)
    await svc.start(123)
    assert svc.has_active_session(123) is True
    assert svc._sessions[123].state == CreationState.AWAITING_BRIEF


async def test_cancel_removes_session():
    svc = make_service()
    await svc.start(123)
    await svc.cancel(123)
    assert svc.has_active_session(123) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: FAIL (`ModuleNotFoundError: src.services.creation_service`).

- [ ] **Step 3: Adicionar config de criação**

Em `src/config.py`, no bloco "General" (após `max_redo_attempts`), adicionar:

```python
    # Criação conversacional (/criar)
    creation_session_timeout: int = Field(1800, alias="CREATION_SESSION_TIMEOUT")
    creation_max_rounds: int = Field(12, alias="CREATION_MAX_ROUNDS")
```

- [ ] **Step 4: Criar o modelo de sessão**

```python
# src/domain/models/creation.py
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .post import ComposedPost


class CreationState(str, Enum):
    AWAITING_BRIEF = "awaiting_brief"
    AWAITING_FOLLOWUP = "awaiting_followup"
    ITERATING = "iterating"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPOSING = "composing"
    AWAITING_PUBLISH = "awaiting_publish"
    AWAITING_CAPTION_FEEDBACK = "awaiting_caption_feedback"
    DONE = "done"
    CANCELLED = "cancelled"


class CreationMode(str, Enum):
    CLEAN = "clean"
    BANNER = "banner"
    AUTO = "auto"


class CreationSession(BaseModel):
    chat_id: int
    post_id: str
    state: CreationState = CreationState.AWAITING_BRIEF
    brief: str = ""
    mode: CreationMode = CreationMode.AUTO
    current_prompt: str = ""
    current_image_path: Optional[str] = None
    rounds: int = 0
    total_cost_usd: float = 0.0
    composed: Optional[ComposedPost] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Criar o esqueleto do serviço**

```python
# src/services/creation_service.py
"""Sessão de criação conversacional de imagem (/criar).

Máquina de estados por chat: conversa (cérebro via ArtDirector) → gera 1 imagem
por rodada (reusa image_generator.generate com template ad-hoc) → ao aprovar,
compõe a legenda (post_composer) e entrega via callback on_complete.
"""
import uuid
from typing import Awaitable, Callable, Optional

from ..domain.models.creation import CreationMode, CreationSession, CreationState
from ..domain.models.post import ComposedPost
from ..utils.logger import get_logger

logger = get_logger(__name__)

OnComplete = Callable[[ComposedPost], Awaitable[None]]


class CreationService:
    def __init__(self, *, brain, art_director, image_generator, brand, budget, post_composer, telegram, settings):
        self._brain = brain
        self._art = art_director
        self._image_generator = image_generator
        self._brand = brand
        self._budget = budget
        self._post_composer = post_composer
        self._telegram = telegram
        self._settings = settings
        self.on_complete: Optional[OnComplete] = None
        self._sessions: dict[int, CreationSession] = {}

    def has_active_session(self, chat_id: int) -> bool:
        s = self._sessions.get(chat_id)
        return s is not None and s.state not in (CreationState.DONE, CreationState.CANCELLED)

    async def start(self, chat_id: int) -> None:
        if not self._brain.available:
            await self._telegram.notify(
                "⚠️ Criação por IA indisponível: configure `BRAIN_PROVIDER`/chave do cérebro."
            )
            return
        if self.has_active_session(chat_id):
            self._sessions.pop(chat_id, None)
            await self._telegram.notify("↺ Recomeçando — a criação anterior foi descartada.")
        self._sessions[chat_id] = CreationSession(chat_id=chat_id, post_id=str(uuid.uuid4()))
        await self._telegram.notify(
            "🎨 Bora criar. O que você quer mostrar?\n"
            "(ex.: 'engrenagem de reposição', 'impressora imprimindo', 'banner: quando vale 3D')"
        )

    async def cancel(self, chat_id: int) -> None:
        if self._sessions.pop(chat_id, None) is not None:
            await self._telegram.notify("❌ Criação cancelada.")
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: PASS (3 passed).

---

### Task 4: Iteração da imagem (brief → gera → ajusta)

**Files:**
- Modify: `src/services/creation_service.py`
- Test: `tests/test_creation_service.py` (estender)

**Interfaces:**
- Consumes: `art_director.build_image_prompt/revise_image_prompt`; `image_generator.generate(...) -> [GeneratedImage]` e `estimate_cost(1) -> float`; `budget.can_spend(x) -> bool`; `brand.image_brief()`; telegram `send_mode_prompt`, `send_creation_preview`, `notify`.
- Produces: `async handle_text(chat_id, text)`, `async set_mode(chat_id, mode: CreationMode)`, `async another_option(chat_id)`, `async request_adjustment(chat_id)`; helper `_build_adhoc_template(prompt) -> PromptTemplate`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_creation_service.py  (adicionar)
import uuid as _uuid
from pathlib import Path
from PIL import Image
from src.domain.models.creation import CreationMode
from src.domain.models.post import GeneratedImage
from src.utils.cost_tracker import BudgetTracker


def _fake_image_generator(tmp_path: Path):
    gen = MagicMock()
    gen.estimate_cost.return_value = 0.04

    async def _generate(template, post_id, count=1, image_brief="", subject=""):
        p = tmp_path / post_id / "raw_0.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 1280), (50, 60, 70)).save(p, format="PNG")
        return [GeneratedImage(id=str(_uuid.uuid4()), post_id=post_id, file_path=str(p),
                               prompt_used=template.prompt, cost_usd=0.04)]
    gen.generate = AsyncMock(side_effect=_generate)
    return gen


def _art():
    a = MagicMock()
    a.build_image_prompt = AsyncMock(return_value="english prompt v1")
    a.revise_image_prompt = AsyncMock(return_value="english prompt v2")
    return a


async def test_brief_then_mode_generates_one_image(tmp_path):
    t = _telegram()
    brand = MagicMock(); brand.image_brief.return_value = "marca"
    svc = make_service(telegram=t, art_director=_art(),
                       image_generator=_fake_image_generator(tmp_path),
                       brand=brand, budget=BudgetTracker(10, 100, 0.8))
    await svc.start(7)
    await svc.handle_text(7, "uma engrenagem")          # vira brief, pede modo
    t.send_mode_prompt.assert_awaited()
    await svc.set_mode(7, CreationMode.CLEAN)            # dispara 1ª geração
    s = svc._sessions[7]
    assert s.state == CreationState.ITERATING
    assert s.rounds == 1 and s.current_image_path
    t.send_creation_preview.assert_awaited()


async def test_feedback_revises_and_regenerates(tmp_path):
    t = _telegram(); art = _art()
    svc = make_service(telegram=t, art_director=art,
                       image_generator=_fake_image_generator(tmp_path),
                       brand=MagicMock(), budget=BudgetTracker(10, 100, 0.8))
    await svc.start(7); await svc.handle_text(7, "engrenagem"); await svc.set_mode(7, CreationMode.AUTO)
    await svc.request_adjustment(7)
    assert svc._sessions[7].state == CreationState.AWAITING_FEEDBACK
    await svc.handle_text(7, "mais escuro")
    art.revise_image_prompt.assert_awaited_with("english prompt v1", "mais escuro")
    assert svc._sessions[7].rounds == 2


async def test_budget_stop_blocks_generation(tmp_path):
    t = _telegram()
    budget = MagicMock(); budget.can_spend.return_value = False
    gen = _fake_image_generator(tmp_path)
    svc = make_service(telegram=t, art_director=_art(), image_generator=gen,
                       brand=MagicMock(), budget=budget)
    await svc.start(7); await svc.handle_text(7, "x"); await svc.set_mode(7, CreationMode.AUTO)
    gen.generate.assert_not_awaited()
    t.notify.assert_awaited()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: FAIL (`AttributeError: ... has no attribute 'handle_text'`).

- [ ] **Step 3: Implementar a iteração**

Adicionar ao `CreationService` (em `src/services/creation_service.py`), incluindo o import no topo:

```python
from ..domain.models.template import PromptTemplate
```

```python
    async def handle_text(self, chat_id: int, text: str) -> None:
        session = self._sessions.get(chat_id)
        if session is None:
            return
        text = text.strip()
        if not text:
            return
        if session.state == CreationState.AWAITING_BRIEF:
            session.brief = text
            session.state = CreationState.AWAITING_FOLLOWUP
            await self._telegram.send_mode_prompt(chat_id)
        elif session.state == CreationState.AWAITING_FOLLOWUP:
            session.mode = self._infer_mode(text)
            session.brief = f"{session.brief}. {text}".strip(". ")
            await self._first_generation(session)
        elif session.state == CreationState.AWAITING_FEEDBACK:
            session.current_prompt = await self._art.revise_image_prompt(session.current_prompt, text)
            await self._generate_round(session)
        elif session.state == CreationState.AWAITING_CAPTION_FEEDBACK:
            await self.adjust_caption(chat_id, text)

    async def set_mode(self, chat_id: int, mode: CreationMode) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.AWAITING_FOLLOWUP:
            return
        session.mode = mode
        await self._first_generation(session)

    async def another_option(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        await self._generate_round(session)

    async def request_adjustment(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        session.state = CreationState.AWAITING_FEEDBACK
        await self._telegram.notify(
            "✍️ O que ajustar? (ex.: 'mais escuro', 'tira o texto', 'fundo de concreto')"
        )

    async def _first_generation(self, session: CreationSession) -> None:
        session.current_prompt = await self._art.build_image_prompt(session.brief, session.mode.value)
        await self._generate_round(session)

    async def _generate_round(self, session: CreationSession) -> None:
        if session.rounds >= self._settings.creation_max_rounds:
            await self._telegram.notify(
                f"⚠️ Limite de {self._settings.creation_max_rounds} rodadas. Use 👍 para aprovar ou ❌ para cancelar."
            )
            return
        if not self._budget.can_spend(self._image_generator.estimate_cost(1)):
            await self._telegram.notify("⚠️ Orçamento atingido — não dá pra gerar mais imagens agora.")
            return
        template = self._build_adhoc_template(session.current_prompt)
        images = await self._image_generator.generate(
            template=template, post_id=session.post_id, count=1,
            image_brief=self._brand.image_brief(), subject="",
        )
        img = images[0]
        session.current_image_path = img.file_path
        session.rounds += 1
        session.total_cost_usd += img.cost_usd
        session.state = CreationState.ITERATING
        note = f"Rodada {session.rounds} · sessão ${session.total_cost_usd:.3f}"
        await self._telegram.send_creation_preview(session.chat_id, img.file_path, note)

    def _build_adhoc_template(self, prompt: str) -> PromptTemplate:
        return PromptTemplate(
            id="conversational", name="Conversational", prompt=prompt,
            variables={}, caption_template="", hashtag_pool=[], image_count=1,
        )

    @staticmethod
    def _infer_mode(text: str) -> CreationMode:
        low = text.lower()
        if "banner" in low or "texto" in low:
            return CreationMode.BANNER
        if "limpa" in low or "foto" in low or "sem texto" in low:
            return CreationMode.CLEAN
        return CreationMode.AUTO
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: PASS (6 passed).

---

### Task 5: Finalização (aprovar imagem → compor legenda → publicar)

**Files:**
- Modify: `src/services/creation_service.py`
- Test: `tests/test_creation_service.py` (estender)

**Interfaces:**
- Consumes: `post_composer.compose(images, template, post_id, brand, research=None, subject, instruction) -> ComposedPost`; `on_complete(ComposedPost)`.
- Produces: `async accept_image(chat_id)`, `async request_caption_adjustment(chat_id)`, `async adjust_caption(chat_id, feedback)`, `async publish(chat_id)`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_creation_service.py  (adicionar)
from src.domain.models.post import ComposedPost
from src.domain.models.creation import CreationState as CS


def _post_composer(post_id="p"):
    pc = MagicMock()
    async def _compose(images, template, post_id, brand=None, research=None, subject="", instruction=""):
        return ComposedPost(id=post_id, template_id="conversational",
                            composed_image_paths=["x.jpg"], caption="legenda " + instruction,
                            images=list(images), total_cost_usd=0.04)
    pc.compose = AsyncMock(side_effect=_compose)
    return pc


async def _ready_session(tmp_path):
    t = _telegram()
    svc = make_service(telegram=t, art_director=_art(),
                       image_generator=_fake_image_generator(tmp_path),
                       brand=MagicMock(), budget=BudgetTracker(10, 100, 0.8),
                       post_composer=_post_composer())
    await svc.start(7); await svc.handle_text(7, "engrenagem"); await svc.set_mode(7, CreationMode.AUTO)
    return svc, t


async def test_accept_composes_and_previews(tmp_path):
    svc, t = await _ready_session(tmp_path)
    await svc.accept_image(7)
    assert svc._sessions[7].state == CS.AWAITING_PUBLISH
    assert svc._sessions[7].composed is not None
    t.send_creation_final_preview.assert_awaited()


async def test_publish_calls_on_complete_and_ends(tmp_path):
    svc, t = await _ready_session(tmp_path)
    await svc.accept_image(7)
    received = {}
    async def _done(composed):
        received["c"] = composed
    svc.on_complete = _done
    await svc.publish(7)
    assert received["c"].caption.startswith("legenda")
    assert svc.has_active_session(7) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: FAIL (`AttributeError: ... has no attribute 'accept_image'`).

- [ ] **Step 3: Implementar a finalização**

Adicionar ao `CreationService` (incluir `import uuid` já existe no topo; usar `GeneratedImage`):

```python
from ..domain.models.post import GeneratedImage  # adicionar ao import existente de ..domain.models.post
```

```python
    async def accept_image(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.ITERATING:
            return
        session.state = CreationState.COMPOSING
        await self._telegram.notify("✍️ Escrevendo a legenda no tom da marca…")
        composed = await self._compose(session, instruction="")
        session.composed = composed
        session.state = CreationState.AWAITING_PUBLISH
        await self._telegram.send_creation_final_preview(composed)

    async def request_caption_adjustment(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.state != CreationState.AWAITING_PUBLISH:
            return
        session.state = CreationState.AWAITING_CAPTION_FEEDBACK
        await self._telegram.notify("✍️ O que mudar na legenda?")

    async def adjust_caption(self, chat_id: int, feedback: str) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.composed is None:
            return
        composed = await self._compose(session, instruction=feedback)
        session.composed = composed
        session.state = CreationState.AWAITING_PUBLISH
        await self._telegram.send_creation_final_preview(composed)

    async def publish(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None or session.composed is None:
            return
        composed = session.composed
        session.state = CreationState.DONE
        self._sessions.pop(chat_id, None)
        if self.on_complete is not None:
            await self.on_complete(composed)

    async def _compose(self, session: CreationSession, instruction: str) -> ComposedPost:
        image = GeneratedImage(
            id=str(uuid.uuid4()), post_id=session.post_id,
            file_path=session.current_image_path or "", prompt_used=session.current_prompt,
            cost_usd=0.0,
        )
        return await self._post_composer.compose(
            images=[image], template=self._build_adhoc_template(session.current_prompt),
            post_id=session.post_id, brand=self._brand, subject=session.brief, instruction=instruction,
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_creation_service.py -q`
Expected: PASS (8 passed).

---

### Task 6: CreationHandler (callbacks dos botões + teclados)

**Files:**
- Create: `src/handlers/creation_handler.py`
- Test: `tests/test_creation_handler.py`

**Interfaces:**
- Consumes: `CreationService` (métodos `accept_image`, `another_option`, `request_adjustment`, `cancel`, `set_mode`, `publish`, `request_caption_adjustment`); `CreationMode`.
- Produces: `build_creation_keyboard()`, `build_creation_final_keyboard()`, `build_mode_keyboard()`; `CreationHandler(allowed_chat_ids, creation_service).handle_callback(update, ctx)`. Prefixo de callback: `create:`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_creation_handler.py
from unittest.mock import AsyncMock, MagicMock
from src.handlers.creation_handler import (
    CreationHandler, build_creation_keyboard, build_creation_final_keyboard, build_mode_keyboard,
)


def test_keyboards_callback_data():
    kb = build_creation_keyboard()
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert {"create:accept", "create:another", "create:adjust", "create:cancel"} <= set(data)
    fkb = build_creation_final_keyboard()
    fdata = [b.callback_data for row in fkb.inline_keyboard for b in row]
    assert {"create:publish", "create:caption", "create:discard"} <= set(fdata)
    mkb = build_mode_keyboard()
    mdata = [b.callback_data for row in mkb.inline_keyboard for b in row]
    assert {"create:mode:clean", "create:mode:banner", "create:mode:auto"} <= set(mdata)


def _query(data, chat_id=42):
    q = MagicMock()
    q.data = data
    q.answer = AsyncMock()
    q.message = MagicMock(); q.message.chat_id = chat_id
    update = MagicMock(); update.callback_query = q
    return update


async def test_accept_routes_to_service():
    svc = MagicMock(); svc.accept_image = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[42], creation_service=svc)
    await h.handle_callback(_query("create:accept"), MagicMock())
    svc.accept_image.assert_awaited_with(42)


async def test_mode_routes_with_enum():
    from src.domain.models.creation import CreationMode
    svc = MagicMock(); svc.set_mode = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[42], creation_service=svc)
    await h.handle_callback(_query("create:mode:banner"), MagicMock())
    svc.set_mode.assert_awaited_with(42, CreationMode.BANNER)


async def test_unauthorized_ignored():
    svc = MagicMock(); svc.accept_image = AsyncMock()
    h = CreationHandler(allowed_chat_ids=[999], creation_service=svc)
    await h.handle_callback(_query("create:accept", chat_id=42), MagicMock())
    svc.accept_image.assert_not_awaited()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_creation_handler.py -q`
Expected: FAIL (`ModuleNotFoundError: src.handlers.creation_handler`).

- [ ] **Step 3: Implementar o handler e os teclados**

```python
# src/handlers/creation_handler.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..domain.models.creation import CreationMode
from ..utils.logger import get_logger

logger = get_logger(__name__)


def build_creation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Ficou bom", callback_data="create:accept"),
        InlineKeyboardButton("🔁 Outra opção", callback_data="create:another"),
    ], [
        InlineKeyboardButton("✍️ Ajustar", callback_data="create:adjust"),
        InlineKeyboardButton("❌ Cancelar", callback_data="create:cancel"),
    ]])


def build_creation_final_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprovar e publicar", callback_data="create:publish"),
    ], [
        InlineKeyboardButton("✍️ Ajustar legenda", callback_data="create:caption"),
        InlineKeyboardButton("❌ Descartar", callback_data="create:discard"),
    ]])


def build_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Foto limpa", callback_data="create:mode:clean"),
        InlineKeyboardButton("Banner", callback_data="create:mode:banner"),
        InlineKeyboardButton("Deixa a IA decidir", callback_data="create:mode:auto"),
    ]])


class CreationHandler:
    def __init__(self, allowed_chat_ids: list[int], creation_service):
        self._allowed = allowed_chat_ids
        self._svc = creation_service

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        chat_id = query.message.chat_id if query.message else None
        if chat_id not in self._allowed:
            await query.answer("Não autorizado.")
            return
        await query.answer()
        data = query.data
        if data.startswith("create:mode:"):
            mode = data.split(":", 2)[2]
            await self._svc.set_mode(chat_id, CreationMode(mode))
            return
        action = data.split(":", 1)[1]
        routes = {
            "accept": self._svc.accept_image,
            "another": self._svc.another_option,
            "adjust": self._svc.request_adjustment,
            "cancel": self._svc.cancel,
            "publish": self._svc.publish,
            "caption": self._svc.request_caption_adjustment,
            "discard": self._svc.cancel,
        }
        handler = routes.get(action)
        if handler is not None:
            await handler(chat_id)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_creation_handler.py -q`
Expected: PASS (4 passed).

---

### Task 7: Rotear texto livre para a sessão ativa

**Files:**
- Modify: `src/handlers/conversation_handler.py`
- Test: `tests/test_conversation_routing.py`

**Interfaces:**
- Consumes: `CreationService.has_active_session(chat_id)`, `CreationService.handle_text(chat_id, text)`.
- Produces: `ConversationHandler(allowed_chat_ids, subject_callback, creation_service=None)` — quando há sessão ativa, o texto vai para `creation_service.handle_text` e o fluxo "poste sobre X"/redo é pulado.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_conversation_routing.py
from unittest.mock import AsyncMock, MagicMock
from src.handlers.conversation_handler import ConversationHandler


def _update(text, chat_id=42):
    u = MagicMock()
    u.effective_chat = MagicMock(); u.effective_chat.id = chat_id
    u.message = MagicMock(); u.message.text = text
    u.message.reply_to_message = None
    u.message.reply_text = AsyncMock()
    return u


async def test_active_session_captures_text():
    svc = MagicMock(); svc.has_active_session.return_value = True; svc.handle_text = AsyncMock()
    subject_cb = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], subject_callback=subject_cb, creation_service=svc)
    await h.handle_message(_update("mais escuro"), MagicMock())
    svc.handle_text.assert_awaited_with(42, "mais escuro")
    subject_cb.assert_not_awaited()


async def test_no_session_falls_back_to_subject():
    svc = MagicMock(); svc.has_active_session.return_value = False; svc.handle_text = AsyncMock()
    subject_cb = AsyncMock()
    h = ConversationHandler(allowed_chat_ids=[42], subject_callback=subject_cb, creation_service=svc)
    await h.handle_message(_update("poste sobre engrenagens"), MagicMock())
    svc.handle_text.assert_not_awaited()
    subject_cb.assert_awaited()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_conversation_routing.py -q`
Expected: FAIL (`TypeError: __init__() got an unexpected keyword argument 'creation_service'`).

- [ ] **Step 3: Implementar o roteamento**

Em `src/handlers/conversation_handler.py`, alterar o `__init__` para aceitar `creation_service` e adicionar a checagem no topo de `handle_message`:

```python
    def __init__(self, allowed_chat_ids: list[int], subject_callback: SubjectCallback, creation_service=None):
        self._allowed_chat_ids = allowed_chat_ids
        self._subject_callback = subject_callback
        self._creation_service = creation_service
        self._pending_answers: dict[str, asyncio.Future] = {}
        self._question_to_post: dict[str, str] = {}
```

No início de `handle_message`, logo após validar chat/texto (após `if not text: return`):

```python
        # Sessão de criação ativa tem prioridade: o texto livre é o brief/feedback.
        if self._creation_service is not None and self._creation_service.has_active_session(update.effective_chat.id):
            await self._creation_service.handle_text(update.effective_chat.id, text)
            return
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_conversation_routing.py -q`
Expected: PASS (2 passed).

---

### Task 8: Telegram — `/criar`, callbacks `create:*`, previews

**Files:**
- Modify: `src/services/telegram_bot.py`
- Test: `tests/test_telegram_bot.py` (estender)

**Interfaces:**
- Consumes: `CreationHandler.handle_callback`; `build_creation_keyboard`, `build_creation_final_keyboard`, `build_mode_keyboard`.
- Produces: `register_commands(..., cmd_criar=None, creation_handler=None)`; `async send_creation_preview(chat_id, image_path, note) -> str`; `async send_creation_final_preview(post) -> str`; `async send_mode_prompt(chat_id) -> str`.

- [ ] **Step 1: Escrever o teste falho**

```python
# tests/test_telegram_bot.py  (adicionar)
async def test_send_creation_final_preview_uses_final_keyboard(tmp_path):
    from unittest.mock import AsyncMock, MagicMock
    from PIL import Image
    from src.services.telegram_bot import TelegramBotService
    from src.handlers.approval_handler import ApprovalHandler
    from src.domain.models.post import ComposedPost

    settings = MagicMock()
    settings.telegram_chat_id = 42
    settings.telegram_approval_timeout = 10
    svc = TelegramBotService(settings=settings, approval_handler=ApprovalHandler([42]))

    img = tmp_path / "composed_0.jpg"
    Image.new("RGB", (1080, 1350), (10, 20, 30)).save(img, format="JPEG")
    post = ComposedPost(id="abcd1234", template_id="conversational",
                        composed_image_paths=[str(img)], caption="legenda", total_cost_usd=0.04)

    sent = {}
    bot = MagicMock()
    async def _send_photo(**kw):
        sent.update(kw); return MagicMock(message_id=99)
    bot.send_photo = _send_photo
    svc._app = MagicMock(); svc._app.bot = bot

    mid = await svc.send_creation_final_preview(post)
    assert mid == "99"
    data = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]
    assert "create:publish" in data
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_telegram_bot.py -q`
Expected: FAIL (`AttributeError: 'TelegramBotService' object has no attribute 'send_creation_final_preview'`).

- [ ] **Step 3: Implementar registro + previews**

Em `src/services/telegram_bot.py`:

(a) imports — acrescentar:
```python
from ..handlers.creation_handler import (
    build_creation_keyboard, build_creation_final_keyboard, build_mode_keyboard,
)
from telegram.ext import CallbackQueryHandler  # já importado; manter
```

(b) `register_commands` — adicionar parâmetros e registrar (o handler de criação vem ANTES do de aprovação, filtrado por padrão):
```python
    def register_commands(
        self, cmd_start, cmd_status, cmd_history, cmd_schedule, cmd_pause, cmd_resume,
        cmd_force, cmd_metrics, on_message=None, cmd_criar=None, creation_handler=None,
    ) -> None:
        if not self._app:
            raise RuntimeError("Bot not initialized — call start() first")
        self._app.add_handler(CommandHandler("start", cmd_start))
        self._app.add_handler(CommandHandler("status", cmd_status))
        self._app.add_handler(CommandHandler("history", cmd_history))
        self._app.add_handler(CommandHandler("schedule", cmd_schedule))
        self._app.add_handler(CommandHandler("pause", cmd_pause))
        self._app.add_handler(CommandHandler("resume", cmd_resume))
        self._app.add_handler(CommandHandler("force", cmd_force))
        self._app.add_handler(CommandHandler("metrics", cmd_metrics))
        if cmd_criar is not None:
            self._app.add_handler(CommandHandler("criar", cmd_criar))
        if creation_handler is not None:
            self._app.add_handler(CallbackQueryHandler(creation_handler.handle_callback, pattern=r"^create:"))
        self._app.add_handler(CallbackQueryHandler(self._approval_handler.handle_callback))
        if on_message is not None:
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
```

(c) métodos novos:
```python
    async def send_creation_preview(self, chat_id: int, image_path: str, note: str) -> str:
        with open(image_path, "rb") as f:
            msg = await self._app.bot.send_photo(
                chat_id=chat_id, photo=f, caption=f"🎨 {note}",
                reply_markup=build_creation_keyboard(),
            )
        return str(msg.message_id)

    async def send_creation_final_preview(self, post: ComposedPost) -> str:
        path = Path(post.composed_image_paths[0])
        with open(path, "rb") as f:
            msg = await self._app.bot.send_photo(
                chat_id=self._chat_id, photo=f,
                caption=self._build_preview_caption(post), parse_mode="Markdown",
                reply_markup=build_creation_final_keyboard(),
            )
        return str(msg.message_id)

    async def send_mode_prompt(self, chat_id: int) -> str:
        msg = await self._app.bot.send_message(
            chat_id=chat_id, text="Foto limpa da peça ou banner com texto? (ou responda em texto)",
            reply_markup=build_mode_keyboard(),
        )
        return str(msg.message_id)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_telegram_bot.py -q`
Expected: PASS (todos, incluindo o novo).

---

### Task 9: Wiring no main + `_publish_composed` + `cmd_criar`

**Files:**
- Modify: `src/main.py`
- Modify: `src/handlers/command_handler.py`
- Modify: `.env.example` (se ainda não documentado: `CREATION_SESSION_TIMEOUT`, `CREATION_MAX_ROUNDS`)
- Test: verificação por import + suíte (main não é unit-testado neste repo).

**Interfaces:**
- Consumes: tudo das tarefas 1-8.
- Produces: `/criar` operante; `InstagramAgent._publish_composed(composed: ComposedPost)` que persiste e publica via `_publish`.

- [ ] **Step 1: `cmd_criar` no CommandHandler**

Em `src/handlers/command_handler.py`: adicionar `criar_callback` ao `__init__` e o método:
```python
    def __init__(self, allowed_chat_ids, storage, scheduler, force_callback, criar_callback=None):
        self._allowed_chat_ids = allowed_chat_ids
        self._storage = storage
        self._scheduler = scheduler
        self._force_callback = force_callback
        self._criar_callback = criar_callback
```
```python
    async def cmd_criar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update) or self._criar_callback is None:
            return
        await self._criar_callback(update.effective_chat.id)
```

- [ ] **Step 2: Wiring no `InstagramAgent`**

Em `src/main.py`:

(a) imports:
```python
from .services.art_director import ArtDirectorService
from .services.creation_service import CreationService
from .handlers.creation_handler import CreationHandler
```

(b) em `__init__`, após criar `self._caption_generator`/`self._post_composer` e `self._conversation_handler`:
```python
        self._art_director = ArtDirectorService(brain=self._brain, brand=self._brand)
        self._creation_service = CreationService(
            brain=self._brain, art_director=self._art_director,
            image_generator=self._image_generator, brand=self._brand,
            budget=self._budget, post_composer=self._post_composer,
            telegram=self._telegram, settings=settings,
        )
        self._creation_service.on_complete = self._publish_composed
        self._creation_handler = CreationHandler(
            allowed_chat_ids=[settings.telegram_chat_id], creation_service=self._creation_service,
        )
```
E passar `creation_service` ao `ConversationHandler`:
```python
        self._conversation_handler = ConversationHandler(
            allowed_chat_ids=[settings.telegram_chat_id],
            subject_callback=self._subject_generate,
            creation_service=self._creation_service,
        )
```
> Nota: `self._brand` é recarregado em `start()` (linha ~101). Após `self._brand = self._prompts_loader.load()`, reatribuir a marca aos serviços que a capturaram: `self._art_director._brand = self._brand` e `self._creation_service._brand = self._brand` (ou construir esses dois serviços dentro de `start()`, após o load). **Construir em `start()` é mais limpo** — mover o bloco (b) para logo após o load da marca.

(c) em `start()`, no `register_commands`, passar os novos parâmetros:
```python
        self._telegram.register_commands(
            cmd_start=self._command_handler.cmd_start,
            cmd_status=self._command_handler.cmd_status,
            cmd_history=self._command_handler.cmd_history,
            cmd_schedule=self._command_handler.cmd_schedule,
            cmd_pause=self._command_handler.cmd_pause,
            cmd_resume=self._command_handler.cmd_resume,
            cmd_force=self._command_handler.cmd_force,
            cmd_metrics=self._command_handler.cmd_metrics,
            on_message=self._conversation_handler.handle_message,
            cmd_criar=self._command_handler.cmd_criar,
            creation_handler=self._creation_handler,
        )
```
E incluir `criar_callback` ao montar o `CommandHandler`:
```python
        self._command_handler = CommandHandler(
            allowed_chat_ids=[settings.telegram_chat_id],
            storage=self._storage, scheduler=self._scheduler,
            force_callback=self._force_generate,
            criar_callback=self._creation_service.start,
        )
```

(d) método `_publish_composed`:
```python
    async def _publish_composed(self, composed: ComposedPost) -> None:
        """Publica um post vindo da criação conversacional. O botão 'Aprovar e
        publicar' já fez o papel da aprovação — aqui só persiste e publica."""
        post = Post(**composed.model_dump())
        post.status = PostStatus.AWAITING_APPROVAL
        await self._storage.save_post(post)
        await self._publish(post)
```

- [ ] **Step 3: Documentar envs restantes no `.env.example`**

Acrescentar (se ainda não houver):
```
# Criação conversacional (/criar)
CREATION_SESSION_TIMEOUT=1800
CREATION_MAX_ROUNDS=12
```

- [ ] **Step 4: Verificar import do main + suíte completa**

Run: `python -c "import sys; sys.path.insert(0,'.'); import src.main; print('import OK')"`
Expected: `import OK` (sem erro de assinatura/wiring).

Run: `python -m pytest -q`
Expected: toda a suíte passa (testes antigos + novos).

- [ ] **Step 5: Checklist manual (e2e, exige Telegram + chaves reais)**

Com `BRAIN_PROVIDER=openai`, `OPENAI_API_KEY` e Telegram configurados, rodar o agente e no chat: `/criar` → mandar um brief → escolher modo → ajustar uma vez → `👍` → revisar legenda → `✅ Aprovar e publicar`. Conferir que publica via Buffer e que `/force` e "poste sobre X" seguem funcionando.

---

## Self-Review

**1. Cobertura do spec:**
- §4.1 cérebro configurável → Task 1 ✓
- §4.2 ArtDirectorService → Task 2 ✓
- §4.3 template ad-hoc + generate(count=1) → Task 4 (`_build_adhoc_template`, `_generate_round`) ✓
- §4.4 CreationState/Mode/Session + CreationService (start/cancel/has_active/handle_text/another_option/accept/adjust_caption/publish) → Tasks 3-5 ✓
- §4.5 CreationHandler + roteamento de texto + telegram (/criar, callbacks, previews) → Tasks 6-8 ✓
- §4.6 wiring + `_publish_composed` (sem pesquisa, sem await_approval) → Task 9 ✓
- §5 bordas: brain indisponível (Task 3), orçamento/cap (Task 4), 1 sessão por chat (Task 3), roteamento preservando fluxo atual (Task 7), config nova (Tasks 1/3/9) ✓
- §6 testes com fakes → todas as tasks ✓
- §8 critérios de aceite → cobertos pelas verificações de cada task + checklist e2e (Task 9) ✓

**2. Placeholder scan:** sem "TBD/TODO/etc." Código completo em cada passo. Os passos de "Commit" foram substituídos por gates de `pytest` (não é repo git) — declarado no cabeçalho.

**3. Consistência de tipos/nomes:** `CreationService.__init__` (kwargs `brain, art_director, image_generator, brand, budget, post_composer, telegram, settings`) é o mesmo usado no `make_service` dos testes e no wiring do main. Callbacks `create:accept|another|adjust|cancel|publish|caption|discard|mode:*` batem entre `CreationHandler` (Task 6) e os teclados (Task 6) e o roteamento (Task 8). `on_complete(ComposedPost)` definido na Task 3 e chamado na Task 5, consumido como `_publish_composed` na Task 9. `_build_adhoc_template` definido na Task 4 e reusado na Task 5. Porta `ImageGenerator.generate(template, post_id, count, image_brief, subject)` e `BrainClient.complete(system, prompt, max_tokens)` usadas conforme as assinaturas reais.

**Adaptações:** sem `git commit` (não é repo) — gate por suíte; `main.py` verificado por import + suíte + checklist manual (o repo não tem testes de `main`).
