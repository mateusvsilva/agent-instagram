# Tarefas Backend — Correções pré-primeiro-commit

> Documento de tarefas para o agente **backend-clean-architect**.
> Origem: revisão completa do code-reviewer (2026-06-17), preparando o primeiro commit do repositório impressam.
> Escopo deste doc: **apenas correções de código**. As ações manuais (rotação de chaves de API, conferência de `.gitignore`) ficam com o usuário e estão listadas em "Fora de escopo" no final.

---

## CRÍTICO

### T1 — Corrigir `AttributeError` em todo job agendado
**Arquivos:** `src/main.py:150`, `src/models/schedule.py`

`main.py:150` (dentro de `_handle_scheduled_job`) faz:
```python
max_attempts=schedule.max_attempts,
```
Mas o modelo `Schedule` (`src/models/schedule.py:13`) só define `max_retries` — **não existe** `max_attempts`. Pydantic levanta `AttributeError` ao acessar o atributo inexistente, então **todo job cron quebra** quando o `SchedulerService` o dispara. O agendamento automático (funcionalidade central do produto) está quebrado.

**Atenção à semântica — não são a mesma coisa:**
- `Schedule.max_retries` = retries do job de infraestrutura (APScheduler, em `src/services/scheduler.py`).
- `max_attempts` do pipeline = tentativas de "redo" do `_run_pipeline` (nos outros call sites, linhas `main.py:166` e `main.py:180`, é alimentado por `settings.max_redo_attempts`).

**Decisão a tomar e implementar:**
- **Opção recomendada:** usar `settings.max_redo_attempts` em `_handle_scheduled_job` (consistente com `_force_generate` e `_subject_generate`), eliminando a dependência de um campo no `Schedule`.
- Alternativa: se o agendamento realmente precisa de um número de tentativas próprio, adicionar um campo explícito `max_attempts: int` ao modelo `Schedule` e popular no carregamento dos schedules.

Escolha a opção recomendada salvo se houver requisito de produto que justifique a alternativa. Documente a escolha no commit.

---

## ALTO

### T2 — `brain_model` com model id inválido → IA cai silenciosamente no fallback
**Arquivo:** `src/config.py:26`

```python
brain_model: str = Field("claude-opus-4-8", alias="BRAIN_MODEL")
```
`"claude-opus-4-8"` não é um id de modelo válido da API Anthropic. A chamada em `AnthropicBrainClient.complete` (`src/services/brain_client.py`) falha, mas o erro é engolido por `except Exception` em `market_research.py` e `caption_generator.py`, que caem no template/placeholder. Resultado: **pesquisa de mercado e legenda por IA nunca funcionam de verdade**, mesmo com `ANTHROPIC_API_KEY` válida — e ninguém vê erro óbvio.

**Correção:**
1. Trocar o default por um model id **válido e atual** da API Anthropic (ex.: um `claude-opus-4-...` ou `claude-sonnet-4-...` real). Consulte a skill/documentação de modelos antes de fixar o id — não chute.
2. Melhorar a observabilidade: hoje, "modelo inexistente" (erro 4xx da Anthropic) é indistinguível de "sem API key". Logar o erro real em nível visível (warning/error com o motivo) em vez de engolir silenciosamente, ou notificar o operador. Não remova o fallback — apenas torne a falha visível.

### T3 — `validate_carousel` rejeita post de imagem única (`image_count=1`)
**Arquivos:** `src/utils/image_processing.py:101-108`, `src/services/post_composer.py:38`

`validate_carousel` exige no mínimo 2 imagens (`ValueError: Carousel requires at least 2 images`). Mas `PromptTemplate.image_count` (`src/models/template.py:17`) é configurável e scripts usam `--count` com default 1. Se um template/chamada usar `image_count=1`, `PostComposerService.compose` chama `validate_carousel` e o post inteiro falha.

**Correção:**
1. **Confirmar com produto** se "post de imagem única" é caso suportado (provavelmente sim).
2. Se sim: ajustar o fluxo para aceitar 1+ imagens — ex.: constante `MIN_CAROUSEL_IMAGES` configurável, ou caminho separado para post single-image vs. carrossel em `post_composer.py`. Não force carrossel onde uma imagem basta.

---

## MÉDIO — Números mágicos e configurabilidade

### T4 — Extrair delays/retries mágicos para `Settings` (ou constantes nomeadas)
Padronizar e tornar configurável sem redeploy. Itens:

| Arquivo:linha | Valor | Ação |
|---|---|---|
| `src/services/scheduler.py:140` | `await asyncio.sleep(300)` | Nomear + tornar configurável (retry backoff do job, 5 min fixos hoje). |
| `src/services/gemini_image_generator.py:24` | `_RATE_LIMIT_DELAY = 2.0` | Já é constante; avaliar mover para `Settings` como os demais params do Gemini. |
| `src/services/image_generator.py:19` | `_DALL_E_RATE_LIMIT_DELAY = 9.0` | Idem. |
| `src/services/instagram_publisher.py:13-15` | `_HUMAN_ACTION_DELAY`, `_BACKOFF_BASE`, `_MAX_RETRIES` | Já são constantes; ok manter, mas avaliar reuso da lógica de backoff (duplicada com `scheduler.py`). |
| `src/services/command_handler.py:64` | `limit = 10` (no `/history`) | Promover a constante de módulo ou parâmetro. |

Prioridade: `scheduler.py:140` e `command_handler.py:64` são os mais "soltos". Os já-nomeados são opcionais — não introduza configurabilidade que ninguém vai usar; use bom senso.

### T5 — `remove_job` engole exceções silenciosamente
**Arquivo:** `src/services/scheduler.py:65-67`

`except Exception: pass` mascara erros reais do APScheduler (ex.: falha de jobstore). Adicionar ao menos um `logger.debug`/`logger.warning` com o erro.

---

## BAIXO

### T6 — Comentário com caminho absoluto da máquina do dev
**Arquivo:** `requirements.txt:14` — comentário `pip install -e C:\git\instagrapi`. Remover/generalizar antes do commit (não portátil).

### T7 — Atualizar README desatualizado
**Arquivo:** `README.md:34-36, 141, 161`
- Descreve OpenAI/DALL-E como stack/modelo padrão, mas o default já é `gemini` (`config.py:16`, `.env.example:2`).
- Linha 141 cita diretório `hub/` na raiz que **não existe** no filesystem. Remover a referência morta ou criar/documentar corretamente.

---

## Fora de escopo deste documento (ações manuais do usuário)
- **Rotacionar `GEMINI_API_KEY`** (histórico de exposição registrado em `COMO_RODAR.md:169`) e, por precaução, `OPENAI_API_KEY` / `BUFFER_API_KEY` / `CLOUDINARY_API_SECRET`.
- Conferir, após `git init`, que `.env` aparece como **ignored** (não untracked) antes do primeiro `git add`. Nunca usar `git add -f .env`.
- Decidir se `data/schedules.json` e `.claude/settings.local.json` devem ser versionados ou ignorados.
- Avaliar resetar `data/db/agent.db` (12 posts de teste) antes de começar a versionar.

---

## Ordem sugerida de execução
1. **T1** (crítico, quebra agendamento).
2. **T2** (alto, IA silenciosamente inoperante).
3. **T3** (alto, post single-image).
4. **T4, T5** (médio).
5. **T6, T7** (baixo, higiene).

Rodar os testes existentes (`tests/`) após cada bloco. Não fazer o commit — apenas deixar o working tree pronto para o usuário revisar e commitar.
