# Arquitetura-alvo — Agente impressam

> Documento de arquitetura. A auditoria de 2026-06-17 encontrou a base **saudável** (já existe um
> padrão de "portas plugáveis" deliberado); os itens abaixo são melhorias de separação de
> responsabilidades, não uma reescrita.
>
> **Status (atualizado 2026-06-22):** os passos **1** (criar `domain/ports/` com `Protocol`s) e **2**
> (mover `src/models/` → `src/domain/models/`) da migração da Seção 6 **já foram feitos** — as portas
> são explícitas hoje (`src/domain/ports/`). Faltam os passos **3** (extrair `Notifier`), **4**
> (extrair o pipeline para `application/`), **5** (reorganizar `services/` em `infrastructure/`) e
> **6** (reorganizar `data/`). O texto abaixo descreve o estado-alvo completo.

## 1. Contexto / Problema

O agente hoje funciona e segue um bom princípio: provedores intercambiáveis por configuração
(`IMAGE_PROVIDER`, `IMAGE_HOST_BACKEND`) com fábricas (`build_*`). Pontos
plugáveis bem desenhados: `BrainClient`, `MarketResearchProvider`, `BriefingRepository`,
`ImageUploader`, e os geradores de imagem (Gemini/DALL-E) compartilham a mesma interface implícita.

O que pede atenção arquitetural:

1. **`src/main.py` acumula papéis demais (~430 linhas).** Ele é, ao mesmo tempo:
   - **Composition root** (instancia e injeta todas as dependências);
   - **Seletor de provider** (`_build_image_generator`, `_build_publisher`);
   - **Orquestrador do pipeline** (`_run_pipeline`, `_generate_and_compose`, `_publish`);
   - **Adaptador de Telegram** (monta textos de notificação, formata mensagens de erro).

   Isso é um "God object": a regra de negócio do pipeline está acoplada à infraestrutura de
   inicialização e à camada de apresentação (strings de Telegram). Testar o pipeline isolado exige
   subir quase tudo.

2. **Interfaces (portas) implícitas.** Gemini e DALL-E têm a mesma assinatura por convenção, não por
   um contrato explícito. Idem para os publishers. Não há um `Protocol`/ABC que documente e garanta
   o contrato — o alinhamento depende de disciplina manual.

3. **Camada de apresentação misturada com orquestração.** Strings como
   `f"❌ Pesquisa de mercado falhou para ..."` vivem dentro do pipeline. Mudar o canal de aprovação
   (ex.: do Telegram para o Hub) exigiria mexer na lógica de negócio.

4. **`data/` mistura código-de-configuração com dados de runtime.** `templates/` e `schedules.json`
   são configuração de entrada; `db/`, `images/`, `agent.log` são saída/estado. Estão no mesmo nível.

Nenhum desses pontos é bug — o sistema entrega. São melhorias de manutenibilidade que ficam mais
baratas de fazer **antes** das novas features do `scopes/backend.md` (pesquisa de mercado, legenda
por IA, refazer conversacional), que vão adicionar mais lógica ao pipeline.

## 2. Decisão arquitetural

Adotar uma **arquitetura em camadas com portas explícitas (estilo hexagonal leve)**, mantendo o
projeto simples (sem framework de DI, sem over-engineering). Três camadas:

- **`domain`** — modelos e contratos (portas). Sem dependência de infraestrutura.
- **`application`** — casos de uso / orquestração do pipeline. Depende só de `domain` (portas).
- **`infrastructure`** — adaptadores concretos (Gemini, DALL-E, Buffer, Cloudinary, Telegram, SQLite).
  Implementa as portas de `domain`.

O `main.py` vira um **composition root fino**: só lê config, monta os adaptadores e injeta no caso
de uso. A apresentação (textos de Telegram) sai do pipeline e vira responsabilidade de um
**notifier** com interface própria.

## 3. Estrutura de pastas alvo

```
src/
├── main.py                      # composition root fino: config → wiring → run
├── config.py                    # (mantém) Settings via pydantic-settings
│
├── domain/                      # contratos + modelos puros (zero infra)
│   ├── models/                  # (vem de src/models/) brand, content, post, schedule, template, enums
│   └── ports/                   # Protocols/ABCs que hoje são implícitos
│       ├── image_generator.py   # ImageGenerator (Gemini e DALL-E implementam)
│       ├── publisher.py         # Publisher (Buffer implementa)
│       ├── image_uploader.py    # ImageUploader (Cloudinary)
│       ├── brain.py             # BrainClient
│       ├── market_research.py   # MarketResearchProvider
│       ├── briefing.py          # BriefingRepository
│       └── notifier.py          # Notifier (Telegram hoje; Hub no futuro)
│
├── application/                 # casos de uso (orquestração, sem strings de UI)
│   ├── pipeline.py              # GeneratePostUseCase: pesquisa→imagem→compose→aprovação→publica
│   └── triggers.py              # força/assunto-livre/agendado → entradas do pipeline
│
└── infrastructure/              # adaptadores concretos (implementam domain/ports)
    ├── image/                   # gemini_image_generator.py, dalle_image_generator.py (era image_generator.py)
    ├── publishing/              # buffer_publisher.py, image_host.py
    ├── brain/                   # brain_client.py, market_research.py, caption_generator.py
    ├── persistence/             # storage.py (SQLite), briefing_repository.py
    ├── composition/             # post_composer.py, prompts_loader.py, image_processing.py
    ├── scheduling/              # scheduler.py
    └── telegram/                # telegram_bot.py, handlers/, telegram_notifier.py (impl. de Notifier)
                                 #   handlers/: approval_handler, command_handler, conversation_handler

data/
├── config/                      # ENTRADAS versionáveis (mover para cá)
│   ├── templates/               # era data/templates/
│   └── schedules.json           # era data/schedules.json
└── runtime/                     # SAÍDAS/estado (gitignored)
    ├── db/                      # era data/db/
    ├── images/                  # era data/images/
    └── agent.log                # era data/agent.log
```

> Observação: a separação `data/config` vs `data/runtime` é opcional e de menor prioridade. Se for
> adotada, atualizar os defaults em `config.py` (`templates_dir`, `db_path`, `images_dir`, etc.) e o
> `.gitignore`. Não é pré-requisito das demais mudanças.

## 4. Responsabilidades por camada

| Camada | Responsabilidade | Pode depender de | NÃO pode |
|---|---|---|---|
| `domain` | Modelos + contratos (portas). Regras invariantes de entidade. | nada (só stdlib/pydantic) | infra, SDKs externos |
| `application` | Orquestrar o pipeline usando **apenas portas**. Decisões de fluxo (redo, expiração, budget). | `domain` | SDKs (openai, genai, telegram), I/O direto |
| `infrastructure` | Falar com mundo externo. Implementar portas. Traduzir erros externos em erros de domínio. | `domain`, SDKs | `application` (não importa de cima) |
| `main.py` | Ler config, instanciar adaptadores, injetar, iniciar. | tudo | conter regra de negócio |

**Regra de dependência:** as setas apontam para dentro. `infrastructure` e `application` dependem de
`domain`; `domain` não depende de ninguém. `main.py` é o único lugar que conhece todos.

## 5. Contratos (portas) a tornar explícitos

Hoje implícitos — transformar em `typing.Protocol` em `domain/ports/`. Exemplo do contrato que
Gemini e DALL-E já cumprem de fato:

```python
# domain/ports/image_generator.py
from typing import Protocol
from ..models.post import GeneratedImage
from ..models.template import PromptTemplate

class ImageGenerator(Protocol):
    async def generate(
        self, template: PromptTemplate, post_id: str,
        count: int | None = None, image_brief: str = "", subject: str = "",
    ) -> list[GeneratedImage]: ...
    async def regenerate(self, template: PromptTemplate, post_id: str, count: int | None = None) -> list[GeneratedImage]: ...
    def estimate_cost(self, count: int, quality: str | None = None) -> float: ...
```

```python
# domain/ports/notifier.py — extrai as strings de Telegram do pipeline
from typing import Protocol
from ..models.post import ComposedPost
from ..models.enums import ApprovalStatus

class Notifier(Protocol):
    async def send_preview(self, post: ComposedPost) -> int: ...
    async def await_approval(self, post_id: str) -> ApprovalStatus: ...
    async def notify(self, message: str) -> int: ...
```

Benefício do `Notifier`: o pipeline deixa de saber que existe Telegram. Quando a aprovação migrar
para o Hub (`scopes/frontend.md`), basta um novo adaptador — zero mudança em `application/`.

## 6. Passo a passo da migração (incremental, sem big-bang)

Cada passo é mergeável sozinho e mantém os testes verdes.

1. ✅ **(FEITO) Criar `domain/ports/` com os `Protocol`s** dos contratos já existentes (imagem, publisher,
   uploader, brain, research, briefing). Não muda comportamento; só documenta e habilita type-check.
2. ✅ **(FEITO) Mover `src/models/` → `src/domain/models/`** e ajustar imports. Mecânico, sem lógica.
3. **Extrair `Notifier`**: criar `infrastructure/telegram/telegram_notifier.py` que envolve
   `telegram_bot.py`; trocar as chamadas diretas a Telegram dentro de `main.py` por `self._notifier`.
   As strings de mensagem passam para o adaptador (ou para um módulo de mensagens dedicado).
4. **Extrair o pipeline para `application/pipeline.py`** como `GeneratePostUseCase`, recebendo as
   portas por construtor. `main.py` passa a só instanciar e chamar `use_case.run(...)`.
5. **Reorganizar `src/services/` em `src/infrastructure/<subpasta>/`** conforme a árvore alvo.
   Renomear `image_generator.py` → `infrastructure/image/dalle_image_generator.py` para simetria com
   o Gemini. Atualizar as fábricas `build_*` (que podem ficar em `main.py` ou num `wiring.py`).
6. **(Opcional) Reorganizar `data/`** em `config/` vs `runtime/` e atualizar defaults + `.gitignore`.

Ordem recomendada de prioridade: os passos **3 → 4** (Notifier + extrair o pipeline) trazem o maior
ganho restante (testabilidade do pipeline e desacoplamento da apresentação). Os passos 1 e 2 já estão
concluídos; 5 e 6 são higiene estrutural e podem ser feitos quando convier.

## 7. Tradeoffs / Alternativas consideradas

- **Manter como está (status quo).** Prós: zero esforço, sistema funciona. Contras: cada nova feature
  do pipeline engrossa o `main.py` e amarra mais a regra de negócio ao Telegram. Rejeitado porque as
  features previstas (pesquisa, legenda IA, redo conversacional) vão piorar o acoplamento.
- **Hexagonal "completo" com DI container.** Prós: pureza. Contras: over-engineering para o tamanho do
  projeto; adiciona dependência e cerimônia. Rejeitado por YAGNI/KISS.
- **Hexagonal leve (escolhido).** Camadas + `Protocol`s nativos + composition root manual. Pega 90% do
  benefício (testabilidade, troca de adaptadores) com complexidade baixa e sem dependências novas.

## 8. Orientações por time

**Para o Backend:**
- Antes de implementar as histórias de `scopes/backend.md`, fazer os passos 1, 3 e 4 desta migração —
  isso dá um `GeneratePostUseCase` testável onde as novas etapas (pesquisa, legenda IA, redo) entram
  como métodos/colaboradores claros, não como mais blocos dentro de `main.py`.
- Todo novo provedor/adaptador deve **implementar um `Protocol` de `domain/ports/`**, nunca um
  contrato implícito.
- Nenhuma string de UI/Telegram dentro de `application/`. Mensagens ao operador passam pelo `Notifier`.

**Para o Frontend (Hub):**
- A área de briefing (`scopes/frontend.md`) consome/produz dados via a porta `BriefingRepository`. O
  contrato dessa porta é o ponto de integração — alinhar o formato do briefing (assunto + janela de
  vigência) com o backend antes de implementar a tela.
- A futura aprovação via Hub deve implementar a porta `Notifier`, espelhando o que o Telegram faz —
  não criar um caminho paralelo no pipeline.

## 9. Convenções afetadas

- **Imports**: passam a refletir as camadas (`from ..domain.ports...`, `from ..infrastructure...`).
- **Nomeação**: adaptadores de imagem ganham simetria (`*_image_generator.py`). Fim do nome genérico
  `image_generator.py` para o caso específico do DALL-E.
- **Testes**: testes de `application/` passam a usar fakes que implementam as portas, sem tocar
  SDKs reais — eliminando as 2 falhas pré-existentes ligadas a event loop/infra do Windows.
