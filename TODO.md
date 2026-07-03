# ✅ TO-DO — Agente impressam

> Lista de tarefas para colocar o agente no ar e entregar.
> Marque `[x]` ao concluir. Ordem = de cima para baixo.
> 🔴 destrava o que já existe · 🟢 funcionalidade nova · 🟡 conteúdo da marca
>
> **Atualizado em 2026-06-22:** auditoria de código confirmou que TODA a Seção 2
> ("Funcionalidades novas") já está implementada no código e coberta por testes
> (46 passando). O que sobra são: configuração operacional sua (Seção 1),
> decisões de produto ainda abertas e o Hub (Seção 4).

---

## 🔴 1. Configuração — VOCÊ (destrava o MVP que já está pronto)

> O código está pronto; estes itens são credenciais/ambiente que só você tem.

- [ ] **Telegram bot** (@BotFather): preencher `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` no `.env`
      *(hoje o `.env` está com placeholder — é o que falta para rodar o agente ao vivo)*
- [ ] **Gemini (imagem):** ativar billing no Google se for usar Gemini como provedor de imagem
      → https://aistudio.google.com · teste: `python -m scripts.test_gemini --prompt "teste"`
      *(alternativa já funcional: `IMAGE_PROVIDER=openai` usa DALL-E/gpt-image)*
- [ ] **Rodar ponta a ponta sem Telegram:** `python -m scripts.test_end_to_end --prompt "..."`
      *(dry-run por padrão; Gemini→Cloudinary→Buffer)*
- [ ] **Rodar o agente completo:** `python -m src.main` → no Telegram `/criar` ou `/force` → aprovar

> Buffer e Cloudinary já estavam configurados e testados na última verificação.

---

## 🟢 2. Funcionalidades do "agente inteligente" — ✅ IMPLEMENTADAS

> Estavam como "a fazer" em versões anteriores deste arquivo; a auditoria de
> 2026-06-22 confirmou que estão no código. Mantidas aqui como registro do que
> existe (com o ponto de atenção de cada uma).

- [x] **Pedido por assunto no Telegram** ("poste sobre X") — `conversation_handler.py` + `main._subject_generate`
- [x] **Pesquisa de mercado antes de criar** — `market_research.py`
      ⚠️ fonte ainda é STUB (usa o "cérebro"/LLM, não busca real) — ver DA-02 na Seção 3
- [x] **Legenda gerada por IA, única por post** — `caption_generator.py` (com fallback p/ template)
- [x] **Refazer com pergunta (loop)** — `main._ask_redo_instruction` + `conversation_handler.py`
      ⚠️ refinamento aberto: ao estourar o timeout, a notificação não diz explicitamente
      que regenerou *sem* a instrução (RN-BACKEND-04.1) — hoje a mensagem é genérica
- [x] **Pasta `prompts/` conectada ao código** — `prompts_loader.py` → `BrandIdentity` guia imagem e texto
- [x] **Criação conversacional `/criar`** — `creation_service.py` (fluxo guiado de imagem→legenda→publicar)
- [x] **Briefing semanal (lado backend)** — `briefing_repository.py`
      ⚠️ fonte é STUB (JSON local); falta o Hub gravar de verdade — ver Seção 4
- [x] **Script de teste ponta a ponta** — `scripts/test_end_to_end.py`

---

## 🟡 3. Conteúdo da marca — ✅ PREENCHIDO (revisar quando quiser)

- [x] `prompts/identity.md`, `prompts/image_guidelines.md`, `prompts/caption_guidelines.md`,
      `prompts/hashtag_strategy.md` — todos preenchidos (sem marcadores `> PREENCHER:`)
- [ ] Revisão fina de tom/estilo conforme os primeiros posts reais saírem (iterativo)

---

## 🧭 4. Decisões de produto e Hub (ainda abertas)

- [ ] **DA-02 — Fonte da pesquisa de mercado:** web aberta vs. fontes do nicho?
      Hoje é stub via LLM; trocar `StubMarketResearchProvider` pela fonte real quando decidido.
- [ ] **DA-05 — Onde mora o briefing semanal:** arquivo, banco do Hub, outro?
      Hoje é JSON local (`data/briefing.json`); a porta `BriefingRepository` já isola isso.
- [ ] **Hub (frontend):** área para briefing/aprovação. Não existe no repositório atual.
      Quando existir, a aprovação deve implementar a mesma porta de notificação, não um caminho paralelo.
- [ ] **Aprovação:** manter Telegram (recomendado) ou modo auto-publicar?

---

## 🧹 5. Saúde do código (auditoria 2026-06-22)

- [x] Remover código morto (`apply_watermark`, `estimate_batch_cost`, `regenerate`, wrapper `validate_carousel`)
- [x] Unificar geradores de imagem numa base comum (`BaseImageGenerator`) — fim da duplicação de prompt/budget
- [x] Remover o publisher legado instagrapi (código, scripts, testes, config e docs) — backend único agora é o Buffer
- [ ] **(Proposto, maior) Quebrar o `main.py`** (~470 linhas, "God object") em um caso de uso de
      pipeline + um notificador, conforme `ARQUITETURA.md`. Decisão sua antes de executar.
