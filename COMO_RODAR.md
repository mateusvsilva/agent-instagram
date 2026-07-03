# impressam Agent — Como Rodar e Plano de Entrega

> Estado verificado em **2026-06-15** (rodando os testes e os scripts de verificação).
> Este doc tem 3 partes: **(1) o que funciona hoje**, **(2) como rodar**, **(3) plano para amanhã**.

---

## 1. Fluxo-alvo do agente (a visão completa)

> Legenda de status: ✅ já funciona · ⚠️ existe parcialmente · ❌ ainda a desenvolver

**Como o post começa (2 gatilhos):**
- **A) Por horário** — o scheduler dispara nos horários que você definir. ✅
- **B) Por pedido seu no Telegram** — você manda "poste sobre X" e o agente começa. ❌

**Etapas depois do gatilho:**

```
1. Definir o ASSUNTO do post
     • assunto do "cérebro"/briefing da semana ........... ⚠️ (hoje vem de templates fixos)
     • OU o assunto que você mandou no Telegram .......... ❌
2. Pesquisa de mercado sobre o assunto ................... ❌
3. Gera a IMAGEM (Gemini) ............................... ✅
4. Gera o TEXTO/legenda com IA .......................... ❌ (hoje é texto fixo do template)
5. Envia para REVISÃO no Telegram ....................... ✅
6. Você decide com 3 botões:
     • ✅ Aceitar  → manda publicar ...................... ✅
     • ❌ Recusar  → cancela o processo ................. ✅
     • 🔄 Refazer  → PERGUNTA o que mudar, refaz, reenvia  ⚠️ (botão existe; hoje refaz sem perguntar)
7. Publica no Instagram (Cloudinary hospeda → Buffer) .... ✅
```

**O "cérebro" da IA / briefing semanal (no Hub):**
- Uma área no Hub onde você **conversa com a IA** e diz: "essa semana, a partir do dia tal,
  quero postar sobre tal assunto". ❌
- Isso vira um **guia** que entra no cérebro (pasta `prompts/`) e direciona a pesquisa e os
  posts da semana. ❌ *(a pasta `prompts/` já existe como base — ✅)*

Resumo do que já roda hoje: **Gemini cria a imagem → você aprova no Telegram → Cloudinary hospeda → Buffer publica.** O resto (pedido por assunto, pesquisa de mercado, texto por IA, refazer com pergunta, briefing no Hub) está no **roadmap da Parte B** (seção 6).

---

## 2. Estado atual (o que funciona / não funciona)

| Componente | Status | Observação |
|---|---|---|
| **Publicação (Buffer)** | ✅ **Funciona** | Testado: post de teste entrou na fila. Canal `@theneuralforge` conectado. |
| **Geração de imagem (Gemini)** | ⚠️ **Código pronto, bloqueado** | Chave válida, mas o modelo de imagem **não tem cota grátis** → precisa **ativar billing** (erro 429 RESOURCE_EXHAUSTED). |
| **Hospedagem de imagem (Cloudinary)** | ❌ **Falta configurar** | **Obrigatório** para o agente postar as imagens que ELE gera (Buffer só aceita URL pública). |
| **Aprovação (Telegram)** | ❌ **Token placeholder** | **Obrigatório** para rodar o agente completo (`python -m src.main`). |
| **Prompts / identidade da marca** | ⚠️ **Estrutura criada, vazia** | Pasta `prompts/` com os `> PREENCHER:`. Ainda não conectada ao código. |
| **Testes automatizados** | ✅ **23 passam / 2 falham** | As 2 falhas são pré-existentes (event loop do Windows), não afetam o uso. |

**Tradução:** a parte de **publicar já está pronta**. Falta **desbloquear o Gemini (billing)**, **configurar Cloudinary** e **Telegram** para o agente rodar sozinho de ponta a ponta.

---

## 3. Pré-requisitos (contas e chaves)

| Conta | Para quê | Status |
|---|---|---|
| Python 3.11 | rodar tudo | ✅ instalado |
| Dependências (`pip install -r requirements.txt`) | libs | ✅ ok (google-genai já instalado) |
| **Buffer** (chave + canal IG conectado) | publicar | ✅ configurado |
| **Google AI Studio + BILLING** | gerar imagem | ⚠️ chave ok, **falta billing** |
| **Cloudinary** (grátis) | hospedar imagem | ❌ falta criar/configurar |
| **Telegram Bot** (via @BotFather) | aprovar posts | ❌ falta criar/configurar |

---

## 4. O que falta no `.env`

```
GEMINI_API_KEY=........        # ✅ preenchido (mas precisa de billing na conta Google)
BUFFER_API_KEY=........        # ✅ ok
BUFFER_CHANNEL_ID=........     # ✅ ok
CLOUDINARY_CLOUD_NAME=         # ❌ preencher
CLOUDINARY_API_KEY=           # ❌ preencher
CLOUDINARY_API_SECRET=        # ❌ preencher
TELEGRAM_BOT_TOKEN=placeholder # ❌ trocar pelo token real do @BotFather
TELEGRAM_CHAT_ID=123456        # ❌ trocar pelo seu chat id real
```

---

## 5. Como rodar — passo a passo

### 5.1 Sempre comece pela pasta do agente
```powershell
cd c:\git\impressan
```

### 5.2 Testes isolados (valide UMA peça por vez — recomendado)
```powershell
# A) Publicação (já validado ✅) — lista canais e posta de uma URL pública
python -m scripts.test_buffer

# B) Geração de imagem (rodar DEPOIS de ativar billing no Google)
python -m scripts.test_gemini --prompt "Um cafe aconchegante ao por do sol, foto editorial"
```

### 5.3 Rodar o agente completo (só quando tudo acima estiver verde)
```powershell
python -m src.main
```
> Isso sobe o bot do Telegram + scheduler. No Telegram, use `/force` para gerar um post na hora e aprovar.

---

## 6. PLANO PARA AMANHÃ (checklist em ordem de dependência)

> Faça **na ordem**. Cada fase desbloqueia a próxima. ⏱ = tempo estimado.

### Fase 1 — Desbloquear o Gemini (billing) ⏱ ~15 min  🔴 bloqueia tudo de imagem
- [ ] Entrar em https://aistudio.google.com → projeto da chave
- [ ] Ativar **billing** (vincular a um projeto do Google Cloud com cartão)
- [ ] Rodar `python -m scripts.test_gemini --prompt "..."` → tem que salvar a imagem em `data/images/test-gemini/`
- ✅ **Pronto quando:** o teste imprime `SUCESSO!` e a imagem abre.

### Fase 2 — Configurar a hospedagem de imagem (Cloudinary) ⏱ ~15 min  🔴 bloqueia post de imagem gerada
- [ ] Criar conta grátis em https://cloudinary.com
- [ ] No Dashboard, copiar **Cloud name**, **API Key**, **API Secret**
- [ ] Preencher `CLOUDINARY_*` no `.env`
- ✅ **Pronto quando:** (teste end-to-end da Fase 5 publicar uma imagem gerada).

### Fase 3 — Configurar o Telegram (aprovação) ⏱ ~15 min  🔴 bloqueia o agente completo
- [ ] No Telegram, falar com **@BotFather** → `/newbot` → copiar o **token**
- [ ] Descobrir seu **chat id** (falar com @userinfobot ou similar)
- [ ] Preencher `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env`
- ✅ **Pronto quando:** `python -m src.main` sobe sem erro e o bot responde `/start`.
- 💡 *Alternativa:* se você NÃO quiser aprovação manual, dá pra eu criar um modo
  "auto-publicar" (sem Telegram). Decida na seção 7.

### Fase 4 — Preencher a identidade da marca (prompts) ⏱ ~30-45 min  🟡 qualidade
- [ ] Preencher os `> PREENCHER:` em `prompts/identity.md` (quem é a impressam, público, objetivo)
- [ ] Ajustar `prompts/image_guidelines.md` (estilo visual, cores)
- [ ] Ajustar `prompts/caption_guidelines.md` e `prompts/hashtag_strategy.md`
- ⚠️ *Obs:* a leitura desses arquivos pelo código ainda precisa ser implementada (tarefa minha).
- ✅ **Pronto quando:** os arquivos refletem a marca de verdade.

### Fase 5 — Teste de ponta a ponta ⏱ ~15 min  🟢 validação da entrega
- [ ] Com Fases 1–3 ok: `python -m src.main` → no Telegram `/force` → aprovar
- [ ] Conferir o post na fila do Buffer e no Instagram
- ✅ **Pronto quando:** um post gerado pelo agente aparece no Instagram.
- 💡 Posso criar um script `test_end_to_end.py` (Gemini→Cloudinary→Buffer, sem Telegram) pra facilitar este teste.

### Fase 6 — Entregar / deixar rodando ⏱ ~10 min
- [ ] Definir os horários no `data/schedules.json`
- [ ] Deixar `python -m src.main` rodando (ou agendar)
- ✅ **Pronto quando:** o agente publica sozinho nos horários definidos.

---

## 7. Decisões em aberto (precisam da sua resposta)

1. **Legenda:** IA escreve a legenda a cada post (recomendado) **ou** legenda fixa do template? *(da conversa anterior — ainda pendente)*
2. **Aprovação:** manter Telegram **ou** modo auto-publicar (sem aprovação)?
3. **Hospedagem:** Cloudinary (recomendado) **ou** outro (S3/R2)?
4. **Multi-cliente:** o Buffer hoje só serve para contas que VOCÊ controla. Para
   vários clientes conectarem a conta deles, o caminho é a Graph API da Meta (futuro).

---

## 8. Custos e avisos

- **Gemini (imagem):** ~US$ 0,04 por imagem (sem tier grátis — precisa billing). Um carrossel de 4 ≈ US$ 0,16.
- **Buffer:** plano grátis = 100 requisições/dia (sobra).
- **Cloudinary:** tier grátis generoso.
- 🔐 **Segurança:** a `GEMINI_API_KEY` apareceu em texto no chat — se este histórico for compartilhado, **gere uma nova chave** em https://aistudio.google.com/apikey.
- Com o Buffer, a **senha do Instagram não é mais necessária** no `.env`.
