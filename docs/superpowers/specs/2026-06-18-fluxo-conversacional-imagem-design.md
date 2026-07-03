# Design — Fluxo conversacional de criação de imagem (Telegram)

- **Data:** 2026-06-18
- **Origem:** sessão de brainstorming
- **Status:** aprovado para virar plano de implementação

## 1. Contexto e objetivo

Hoje a criação de conteúdo é "one-shot": `/force` sorteia um template e gera o **post inteiro**
(N imagens + legenda) de uma vez; ou "poste sobre X" faz o mesmo a partir de um assunto livre.
A única interação é aprovar/rejeitar/refazer ([main.py](../../../src/main.py) `_run_pipeline`), e o
🔄 Refazer regenera o post todo.

O operador quer **criar uma imagem conversando com a IA**: dizer o que quer, ver uma imagem,
ajustar por conversa ("mais escuro", "tira o texto", "fundo de concreto"), iterar **uma imagem
barata** por vez até ficar boa, e só então transformá-la em post. Objetivo: um fluxo de autoria
guiado e iterativo, alinhado à marca, dentro do canal que já existe (Telegram).

## 2. Decisões (tomadas na sessão)

| Decisão | Escolha |
|---|---|
| Superfície | **Telegram** — estende o bot atual; reusa aprovação/publicação. |
| Modelo de interação | **Conversa → itera 1 imagem → vira post.** IA faz 1-2 perguntas, gera 1 imagem, refina no loop, depois compõe o post. |
| Cérebro de texto | **Configurável** via `BRAIN_PROVIDER` (openai \| anthropic). Implementar `OpenAIBrainClient` (reusa `OPENAI_API_KEY`); manter Anthropic. Começa no OpenAI. |
| Arquitetura | **Sessão de criação dedicada + reuso do pipeline de publicação** (Abordagem 1). |
| Pesquisa de mercado | **Pulada** no modo conversacional (o brief já é a direção). |
| Geração de 1 imagem | **Template ad-hoc** + `image_generator.generate(count=1)` existente (sem mudar geradores nem a porta). |

## 3. Experiência (UX no Telegram)

Entrada pelo comando **`/criar`** (o "poste sobre X" segue como atalho de tiro rápido). Exemplo:

```
Você:  /criar
Bot:   🎨 Bora criar. O que você quer mostrar?
Você:  uma engrenagem de reposição
Bot:   Foto limpa da peça ou banner com texto? Algum material/fundo?
       [Foto limpa] [Banner] [Deixa a IA decidir]
Você:  foto limpa, aço sobre concreto
Bot:   ⚙️ Gerando… (sessão: $0.04)  [1 imagem]
       [👍 Ficou bom] [🔁 Outra opção] [✍️ Ajustar] [❌ Cancelar]
Você:  ✍️ Ajustar → "mais escuro e de cima"
Bot:   ⚙️ Regenerando… (sessão: $0.08)  [nova imagem]  [👍][🔁][✍️][❌]
Você:  👍 Ficou bom
Bot:   ✍️ Escrevendo legenda…  [PREVIEW final: imagem + legenda + hashtags]
       [✅ Aprovar e publicar] [✍️ Ajustar legenda] [❌ Descartar]
Você:  ✅  →  ✅ Publicado! (via Buffer)
```

**Princípios:** no máx. 1-2 perguntas (resto inferido da marca); itera **uma imagem por vez**;
custo mostrado a cada rodada e respeitando orçamento; post só é composto **depois** que a imagem
está boa; banner → texto curto CAIXA ALTA sem acento (regra do `image_guidelines.md`); post de
**imagem única** no MVP.

## 4. Arquitetura e componentes

Tudo encaixa na arquitetura de portas existente. A porta `BrainClient`
(`available`, `async complete(system, prompt, max_tokens) -> str`) **não muda**.

### 4.1 Cérebro configurável
- **`src/services/brain_client.py`** — novo `OpenAIBrainClient`:
  - `__init__(settings)`: `self._api_key = settings.openai_api_key`, `self._model = settings.openai_brain_model`, client preguiçoso.
  - `available -> bool(self._api_key)`.
  - `async complete(system, prompt, max_tokens=1024) -> str`: `AsyncOpenAI(api_key).chat.completions.create(model, messages=[{role:system},{role:user}], max_tokens)` → extrai `choices[0].message.content`. Import preguiçoso de `openai`.
  - `build_brain_client(settings)`: `provider = (settings.brain_provider or "openai").lower()`; `"anthropic"` → `AnthropicBrainClient`, senão `OpenAIBrainClient`. Mantém o warning quando `not available`.
- **`src/config.py`** + **`.env.example`** — novos campos: `brain_provider: str = "openai"`, `openai_brain_model: str = "gpt-4o-mini"`.

### 4.2 Direção de arte (sobre o cérebro, sem mudar a porta)
- **`src/services/art_director.py`** — `ArtDirectorService(brain, brand)`:
  - `async build_image_prompt(brief: str, mode: str) -> str` — devolve **um prompt de imagem em inglês** seguindo `image_guidelines.md`.
  - `async revise_image_prompt(current_prompt: str, feedback: str) -> str` — devolve o prompt revisado aplicando o feedback (pt-BR) ao prompt atual.
  - System prompt: "diretor de arte de marca de impressão 3D industrial; siga as diretrizes de marca (injetadas); devolva SÓ o prompt, em inglês; se for banner, inclua texto curto em CAIXA ALTA sem acento; nada de explicação".

### 4.3 Geração de 1 imagem (reuso)
- O `CreationService` monta um **`PromptTemplate` ad-hoc**:
  `PromptTemplate(id="conversational", name="Conversational", prompt=<prompt da IA>, caption_template="", hashtag_pool=<pool do pilar ou padrão da marca>, image_count=1)`.
- Chama `image_generator.generate(template=adhoc, post_id=session.post_id, count=1, image_brief=brand.image_brief(), subject="")` — caminho existente, **orçamento já trackeado** por `generate()`. Sem mudança em DALL-E/Gemini nem na porta `ImageGenerator`.

### 4.4 Sessão + serviço (núcleo novo)
- **`src/domain/models/creation.py`**:
  - `class CreationState(str, Enum)`: `AWAITING_BRIEF`, `AWAITING_FOLLOWUP`, `ITERATING`, `AWAITING_FEEDBACK`, `COMPOSING`, `AWAITING_PUBLISH`, `AWAITING_CAPTION_FEEDBACK`, `DONE`, `CANCELLED`.
  - `class CreationMode(str, Enum)`: `CLEAN`, `BANNER`, `AUTO`.
  - `class CreationSession(BaseModel)`: `chat_id:int`, `post_id:str`, `state:CreationState`, `brief:str=""`, `mode:CreationMode=AUTO`, `pillar:str|None=None`, `current_prompt:str=""`, `current_image_path:str|None=None`, `rounds:int=0`, `total_cost_usd:float=0.0`, `composed: ComposedPost|None=None`, `created_at`, `updated_at`. (`composed` guarda o post montado entre o preview final e a publicação.)
- **`src/services/creation_service.py`** — `CreationService`:
  - Deps: `brain: BrainClient`, `art_director: ArtDirectorService`, `image_generator: ImageGenerator`, `brand: BrandIdentity`, `budget: BudgetTracker`, `caption_generator: CaptionGeneratorService`, `telegram: TelegramBotService`, `settings`, e callback `on_complete: Callable[[ComposedPost], Awaitable[None]]`.
  - Estado: `sessions: dict[int, CreationSession]` (em memória).
  - `async start(chat_id)`: se `not brain.available` → avisa e aborta; se já há sessão → oferece cancelar; senão cria sessão `AWAITING_BRIEF` e manda a saudação.
  - `async handle_text(chat_id, text)`: despacha por `state` (brief → talvez follow-up ou 1ª geração; feedback → revisa+regenera; ajuste de legenda → recompõe legenda).
  - `async another_option(chat_id)`: regenera variação nova do mesmo brief.
  - `async accept_image(chat_id)`: estado→`COMPOSING`; compõe `ComposedPost` de 1 imagem (legenda via `caption_generator.generate(subject=brief, brand, template=adhoc, fallback...)`, hashtags do pool), guarda em `session.composed`, envia **preview final** (`send_preview` + `build_creation_final_keyboard`: `create:publish|caption|discard`); estado→`AWAITING_PUBLISH`.
  - `async adjust_caption(chat_id, feedback)`: recompõe a legenda com `instruction=feedback`, atualiza `session.composed`, reenvia o preview final.
  - `async publish(chat_id)`: `await on_complete(session.composed)`; estado→`DONE`.
  - `async cancel(chat_id)`: encerra sessão.
  - `has_active_session(chat_id) -> bool`.
  - Internos: `_generate_round(session)` (checa orçamento + `CREATION_MAX_ROUNDS`, gera 1 imagem, atualiza custo/rodadas, envia preview com botões), `_build_adhoc_template(prompt, pillar)`.

### 4.5 Fiação no Telegram
- **`src/handlers/creation_handler.py`** — `CreationHandler` (análogo ao `ApprovalHandler`): callbacks com chave por `chat_id`.
  - Iteração da imagem: `create:another` → `another_option`; `create:adjust` → seta `AWAITING_FEEDBACK` e pede "o que ajustar?"; `create:accept` → `accept_image`; `create:cancel` → `cancel`.
  - Modo (após o brief): `create:mode:clean|banner|auto` → define `CreationMode` e dispara a 1ª geração.
  - Preview final: `create:publish` → `publish`; `create:caption` → seta `AWAITING_CAPTION_FEEDBACK` e pede o ajuste da legenda; `create:discard` → `cancel`.
- **`src/handlers/conversation_handler.py`** — no início de `handle_message`: se `creation_service.has_active_session(chat_id)` e o estado aguarda texto, `await creation_service.handle_text(chat_id, text)` e retorna **antes** da lógica de redo e de "poste sobre X".
- **`src/handlers/command_handler.py`** — `cmd_criar(update, ctx)` → `creation_service.start(chat_id)`. Adiciona `/criar` ao `cmd_start` (ajuda).
- **`src/services/telegram_bot.py`** — registra `/criar`, registra o callback handler com padrão `create:*`, e adiciona `send_creation_preview(chat_id, image_path, note) -> message_id` (1 foto + `build_creation_keyboard`: `another|adjust|accept|cancel`). Preview final reusa `send_preview` + `build_creation_final_keyboard` (`create:publish|caption|discard`).

### 4.6 Handoff pra publicação (reuso)
- **`src/main.py`** — constrói `ArtDirectorService` e `CreationService`, injeta tudo, e seta `creation_service.on_complete = self._publish_composed`.
  - `async _publish_composed(composed: ComposedPost)`: cria `Post` (de `composed`), `save_post` e `_publish` (Buffer, existente) + notifica. O **botão `create:publish` já é a aprovação** (a sessão de criação fez o papel do preview/aprovação), então aqui **não** há `await_approval` nem pesquisa nem loop de geração — só persistência + publicação.
  - Registra `cmd_criar`; passa `creation_service` ao `ConversationHandler`; registra `CreationHandler` no telegram.

### 4.7 Fluxo de dados
```
/criar → cmd_criar → CreationService.start → sessão(AWAITING_BRIEF) → saudação
texto  → ConversationHandler → (sessão ativa?) → CreationService.handle_text
         → ArtDirector(cérebro) → template ad-hoc → generate(count=1) → send_creation_preview
botão  → CreationHandler → another / adjust / accept / cancel
accept → caption_generator → ComposedPost(1 img) → preview final (create:publish|caption|discard)
publish→ on_complete=_publish_composed → save_post → _publish (Buffer)
```

## 5. Casos de borda e configuração

- **Cérebro indisponível:** `/criar` checa `brain.available` e avisa (aponta `BRAIN_PROVIDER`/chave). Sem falha silenciosa.
- **Orçamento:** antes de cada geração `budget.can_spend`; custo acumulado por sessão; cap suave `CREATION_MAX_ROUNDS` (avisa ao se aproximar) e parada dura se estourar.
- **Concorrência:** 1 sessão por chat; `/criar` com sessão ativa → oferece cancelar; chats independentes.
- **Timeout de inatividade:** `CREATION_SESSION_TIMEOUT` encerra com aviso.
- **Roteamento:** sessão ativa captura o texto; sem sessão, "poste sobre X" e resposta de redo ficam **intactos** (precedência: sessão > resposta de redo > assunto livre).
- **Sessões em memória** (perdidas em restart) — aceitável no MVP; o `Post` final persiste como hoje.
- **Imagem única:** `validate_carousel` já aceita 1 imagem (`MIN_CAROUSEL_IMAGES = 1`) — sem mudança.
- **Provedores independentes:** `IMAGE_PROVIDER` ≠ `BRAIN_PROVIDER`. Banners renderizam melhor com `IMAGE_PROVIDER=gemini`.
- **Config nova:** `BRAIN_PROVIDER`, `OPENAI_BRAIN_MODEL`, `CREATION_SESSION_TIMEOUT` (s, default 1800), `CREATION_MAX_ROUNDS` (default 12).

## 6. Testes (fakes, sem API real)

- `OpenAIBrainClient`: `available` e `complete` (mock do SDK `openai`).
- `ArtDirectorService`: cérebro fake determinístico → `build/revise` devolvem prompt; modo banner injeta "CAIXA ALTA sem acento" no system.
- `CreationService` (cérebro fake + gerador fake): `start`→brief→prompt→gera; ramo de follow-up; feedback→revisa→regera; `another_option`; `accept`→`ComposedPost` de 1 imagem (chama `on_complete`); `cancel`; parada por orçamento/`CREATION_MAX_ROUNDS`; 1 sessão por chat.
- `ConversationHandler`: precedência (sessão ativa > resposta de redo > "poste sobre X").
- `_publish_composed`: caminho feliz com fakes (reusa aprovação + publicação).
- `_build_adhoc_template` gera `PromptTemplate` válido.

## 7. Fora de escopo

- Hub/UI web.
- Montagem de carrossel (iterar várias imagens num post).
- Persistência de sessões entre reinícios.
- Novo provedor de imagem (usa o `IMAGE_PROVIDER` atual).
- Configurar billing/chaves (responsabilidade de operação/`scopes/devops.md`).

## 8. Critérios de aceite

- `/criar` inicia sessão; o cérebro (conforme `BRAIN_PROVIDER`) interpreta o brief; sem cérebro, avisa.
- Cada rodada de ajuste regenera **uma** imagem, mostra custo e respeita orçamento.
- `👍` → legenda no tom da marca → preview final (publicar / ajustar legenda / descartar) → publica via Buffer.
- 1 sessão por chat; `/force` e "poste sobre X" seguem funcionando sem regressão.
- Post de imagem única passa na validação e publica.
- `OpenAIBrainClient` selecionável por env, implementando a porta `BrainClient`.
- Suíte de testes (nova + existente) passa.
