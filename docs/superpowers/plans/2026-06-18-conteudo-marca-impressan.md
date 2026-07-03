# Conteúdo de Marca impressam — Implementation Plan

> **For agentic workers:** este é um plano de **conteúdo** (Markdown + JSON), não de código.
> Não há ciclo TDD red-green (o "teste" de cada tarefa é uma verificação determinística) e
> **não há git** neste diretório (sem passos de commit; os gates de verificação substituem o commit).
> Execute tarefa a tarefa marcando os checkboxes (`- [ ]`).

**Goal:** Substituir o scaffold de marca por conteúdo real — reescrever os 4 `prompts/*.md` e trocar os 2 templates genéricos por 5 alinhados ao negócio (impressão 3D industrial, autoridade técnica).

**Architecture:** Conteúdo puro consumido pelo pipeline **já existente**. `PromptsLoaderService` lê `prompts/*.md` → `BrandIdentity`, injetada nos prompts de imagem (`image_brief()`) e de legenda (`caption_brief()`). Os JSON em `data/templates/` viram `PromptTemplate`. **Nenhuma mudança de código.**

**Tech Stack:** Markdown (prompts), JSON (templates), Python 3.11 + pydantic (validação), pytest (sanidade).

## Global Constraints

- Conteúdo **verbatim** de cada arquivo está no spec `docs/superpowers/specs/2026-06-18-conteudo-marca-prompts-design.md`, em blocos fenced paste-ready (§4.1–§4.4 para os prompts, §5.1–§5.5 para os templates). Copiar de lá é a fonte única de verdade.
- Idioma: diretrizes e legendas em **pt-BR**; o campo `prompt` dos templates em **inglês**.
- **Zero `> PREENCHER:`** pode restar em `prompts/*.md` — `PromptsLoaderService._is_incomplete` marca o arquivo como incompleto e degrada a qualidade.
- **Sem notas meta** dentro dos arquivos de prompt (entram verbatim no prompt do modelo). Lacuna de fato desconhecida → default genérico confiável; o rastreamento fica no spec.
- Texto de banner dentro da imagem: **CAIXA ALTA sem acento** (ex.: `PECA FORA DE LINHA?`).
- Acento visual provisório: **azul técnico `#1B4D7E`**.
- Hashtags proibidas (remover/não usar): `#aiart` `#dalleai` `#generativeart` `#aiartwork`.
- Não é repositório git → sem `git commit`; cada tarefa termina num gate de verificação.

## File Structure

- **Modify** `prompts/identity.md` — identidade/voz base (spec §4.1)
- **Modify** `prompts/image_guidelines.md` — diretrizes visuais + regra de texto-na-imagem (spec §4.2)
- **Modify** `prompts/caption_guidelines.md` — voz da legenda (spec §4.3)
- **Modify** `prompts/hashtag_strategy.md` — estratégia de hashtag (spec §4.4)
- **Create** `data/templates/peca_destaque.json` (spec §5.1)
- **Create** `data/templates/impressora_trabalhando.json` (spec §5.2)
- **Create** `data/templates/problema_solucao.json` (spec §5.3)
- **Create** `data/templates/educativo_tecnico.json` (spec §5.4)
- **Create** `data/templates/bastidor_autoridade.json` (spec §5.5)
- **Delete** `data/templates/abstract_minimalist.json`
- **Delete** `data/templates/sunset_landscape.json`

Nenhum arquivo de código é tocado. Verificado: nenhum teste carrega os JSON de template (os testes constroem `PromptTemplate` inline — `tests/test_post_composer.py:20`, `tests/test_image_generator.py:24`), então remover os 2 antigos não quebra a suíte.

---

### Task 1: Reescrever os 4 arquivos de marca em `prompts/`

**Files:**
- Modify: `prompts/identity.md`, `prompts/image_guidelines.md`, `prompts/caption_guidelines.md`, `prompts/hashtag_strategy.md`
- Fonte do conteúdo: spec §4.1–§4.4 (blocos fenced, copiar verbatim)

**Interfaces:**
- Consumes: nada.
- Produces: `prompts/*.md` completos → `PromptsLoaderService.load()` retorna `BrandIdentity` com `incomplete_sections == []` e `is_complete == True`.

- [ ] **Step 1: Substituir `prompts/identity.md`**
  Substituir TODO o conteúdo do arquivo pelo bloco do spec **§4.1** (verbatim). Conferir que não sobrou nenhum `> PREENCHER:`.

- [ ] **Step 2: Substituir `prompts/image_guidelines.md`**
  Substituir TODO o conteúdo pelo bloco do spec **§4.2** (verbatim). Inclui a regra revisada de texto-na-imagem (texto curto permitido) e o acento `#1B4D7E`.

- [ ] **Step 3: Substituir `prompts/caption_guidelines.md`**
  Substituir TODO o conteúdo pelo bloco do spec **§4.3** (verbatim). Voz especialista direto, emoji zero-a-mínimo, exemplos bom/ruim.

- [ ] **Step 4: Substituir `prompts/hashtag_strategy.md`**
  Substituir TODO o conteúdo pelo bloco do spec **§4.4** (verbatim). Mix marca/nicho/setores/amplas/locais + proibição das hashtags de IA.

- [ ] **Step 5: Verificar — nenhum placeholder restante (gate primário)**
  Rodar (a partir da raiz do repo):
  ```bash
  grep -rn "PREENCHER" prompts/ && echo "FALHOU: ainda há placeholders" || echo "OK: nenhum placeholder"
  ```
  Esperado: `OK: nenhum placeholder` (o `grep` não acha nada → entra no `||`).

- [ ] **Step 6: Verificar — loader reporta marca completa (gate semântico)**
  Rodar (a partir da raiz do repo, mesmo ambiente dos testes):
  ```bash
  python -c "import sys; sys.path.insert(0,'.'); from src.config import Settings; from src.services.prompts_loader import PromptsLoaderService; b=PromptsLoaderService(Settings()).load(); print('incomplete:', b.incomplete_sections); assert b.is_complete, b.incomplete_sections; print('OK: todas as secoes de marca completas')"
  ```
  Esperado: `incomplete: []` seguido de `OK: todas as secoes de marca completas`.
  Se `Settings()` falhar por env ausente, o `.env` da raiz já supre as credenciais; garanta que está rodando na raiz do projeto.

---

### Task 2: Trocar os templates (criar 5, remover 2)

**Files:**
- Create: `data/templates/{peca_destaque,impressora_trabalhando,problema_solucao,educativo_tecnico,bastidor_autoridade}.json`
- Delete: `data/templates/abstract_minimalist.json`, `data/templates/sunset_landscape.json`
- Fonte do conteúdo: spec §5.1–§5.5 (blocos JSON, copiar verbatim)

**Interfaces:**
- Consumes: nada (independente da Task 1).
- Produces: 5 arquivos válidos para `PromptTemplate(**json)` — cada um com `id`, `name`, `prompt`, `caption_template`, `hashtag_pool` (15-20), `image_count`, `active`. Os 2 genéricos não existem mais.

- [ ] **Step 1: Criar `data/templates/peca_destaque.json`** — conteúdo do spec **§5.1** (verbatim).
- [ ] **Step 2: Criar `data/templates/impressora_trabalhando.json`** — spec **§5.2** (verbatim).
- [ ] **Step 3: Criar `data/templates/problema_solucao.json`** — spec **§5.3** (verbatim). `headline` em CAIXA ALTA sem acento.
- [ ] **Step 4: Criar `data/templates/educativo_tecnico.json`** — spec **§5.4** (verbatim). `title` em CAIXA ALTA sem acento.
- [ ] **Step 5: Criar `data/templates/bastidor_autoridade.json`** — spec **§5.5** (verbatim).

- [ ] **Step 6: Remover os 2 templates genéricos**
  ```bash
  rm "data/templates/abstract_minimalist.json" "data/templates/sunset_landscape.json"
  ```

- [ ] **Step 7: Verificar — JSON válido, schema ok, antigos removidos (gate)**
  Rodar (a partir da raiz do repo):
  ```bash
  python -c "import sys,glob,json,os; sys.path.insert(0,'.'); from src.domain.models.template import PromptTemplate; files=sorted(glob.glob('data/templates/*.json')); names=[os.path.basename(f) for f in files]; print(names); ts=[PromptTemplate(**json.load(open(f,encoding='utf-8'))) for f in files]; assert len(files)==5, f'esperado 5, achei {len(files)}'; assert 'abstract_minimalist.json' not in names and 'sunset_landscape.json' not in names; assert all(15<=len(t.hashtag_pool)<=20 for t in ts), 'hashtag_pool fora de 15-20'; print('OK: 5 templates validos, genericos removidos, hashtags 15-20')"
  ```
  Esperado: lista dos 5 nomes, depois `OK: 5 templates validos, genericos removidos, hashtags 15-20`.

---

### Task 3: Sanidade — suíte de testes não regrediu

**Files:** nenhum (somente execução).

- [ ] **Step 1: Rodar a suíte**
  ```bash
  python -m pytest -q
  ```
  Esperado: todos os testes passam (a mudança é só conteúdo; nenhum teste carrega os JSON de template nem os `prompts/*.md`). Se algo falhar, investigar antes de declarar pronto.

---

## Self-Review

**1. Cobertura do spec:**
- §4.1 identity.md → Task 1 Step 1 ✓
- §4.2 image_guidelines.md → Task 1 Step 2 ✓
- §4.3 caption_guidelines.md → Task 1 Step 3 ✓
- §4.4 hashtag_strategy.md → Task 1 Step 4 ✓
- §5.1–§5.5 templates → Task 2 Steps 1-5 ✓
- §6 remoção dos 2 genéricos → Task 2 Step 6 ✓
- §6 "nenhuma mudança de código" → respeitado (nenhuma Task toca `src/`) ✓
- §8 critérios de aceite (sem `PREENCHER`, loader completo, 5 templates ativos, hashtags 15-20) → Task 1 Steps 5-6 e Task 2 Step 7 ✓

**2. Placeholder scan:** sem "TBD/TODO/implementar depois" no plano. As referências "spec §X" apontam para conteúdo verbatim já existente e fechado (não é trabalho indefinido) — escolha de DRY para manter fonte única e evitar drift entre spec e plano.

**3. Consistência de tipos/nomes:** os campos verificados (`id`, `name`, `prompt`, `caption_template`, `hashtag_pool`, `image_count`, `active`) batem com `PromptTemplate` (`src/domain/models/template.py`). Os nomes lógicos (`identity`, `image_guidelines`, `caption_guidelines`, `hashtag_strategy`) batem com `PromptsLoaderService._PROMPT_FILES` e `BrandIdentity`.

**Adaptações ao formato padrão (content task):** sem red-green TDD (verificação determinística no lugar) e sem `git commit` (diretório não é repo). Decisões registradas em Global Constraints.
