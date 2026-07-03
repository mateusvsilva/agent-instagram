# Escopo: DevOps / Configuração — Agente impressam

> Tarefas da Seção "🔴 1. Configuração — VOCÊ" do `TODO.md`. São tarefas de **configuração de
> conta/credencial e validação operacional**, não de desenvolvimento — o código que consome essas
> credenciais já existe (`gemini_image_generator.py`, `image_host.py`, `buffer_publisher.py`,
> `telegram_bot.py` em `agents/impressam/src/`). Entram aqui porque destravam o MVP que já está
> pronto e bloqueiam toda a Seção 2 (funcionalidades novas) do TODO.md.

## Objetivo de negócio

Sair do estado "código pronto mas inoperante por falta de credencial" para "agente publica
de ponta a ponta", sem nenhuma linha de código nova.

## Regras de negócio

- **RN-DEVOPS-01**: O agente não pode operar com credenciais placeholder. Se `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` ou `CLOUDINARY_API_SECRET`
  estiverem vazios ou com valor de exemplo, o fluxo correspondente deve falhar de forma explícita
  (não publicar silenciosamente, não gerar imagem sem hospedagem). *(Já é o comportamento
  documentado no COMO_RODAR.md — aqui é só a confirmação de que a regra deve seguir valendo após
  a configuração real ser feita.)*
- **RN-DEVOPS-02**: A geração de imagem real (Gemini) só deve ser tentada em produção após o
  teste isolado (`python -m scripts.test_gemini`) confirmar sucesso — evita queimar cota/orçamento
  em falha de configuração básica.
- **RN-DEVOPS-03**: Nenhuma chave de API deve ser registrada em texto plano em local
  compartilhável (chat, commit, log). *(Alerta explícito já presente no COMO_RODAR.md: a
  `GEMINI_API_KEY` foi exposta em uma conversa anterior e deve ser rotacionada.)*

---

## HU-DEVOPS-01: Ativar billing do Google para geração de imagem

Como **operador do agente**, quero **billing ativo na conta Google associada à `GEMINI_API_KEY`**,
para que **a geração de imagem via Gemini deixe de falhar com erro de cota (429 RESOURCE_EXHAUSTED)**.

Critérios de Aceite:
- Dado que o billing foi ativado no Google AI Studio, quando o operador rodar
  `python -m scripts.test_gemini --prompt "teste"`, então o comando deve imprimir sucesso e
  salvar a imagem gerada em `data/images/test-gemini/`.
- Dado que o billing não está ativo, quando a geração de imagem for chamada, então o erro
  retornado ao operador deve indicar claramente que é um problema de cota/billing (não um erro
  genérico).

Regras de negócio relacionadas: RN-DEVOPS-02
Prioridade: **Alta** — bloqueia toda geração de imagem real, base de todo o pipeline.
Dependências: nenhuma.
Notas para o arquiteto/devs: nenhuma ação de código esperada aqui; apenas validação operacional.

---

## HU-DEVOPS-02: Configurar Cloudinary para hospedagem de imagem

Como **operador do agente**, quero **uma conta Cloudinary configurada com
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` e `CLOUDINARY_API_SECRET` no `.env`**, para que
**as imagens geradas pelo agente tenham uma URL pública que o Buffer aceite para publicação**.

Critérios de Aceite:
- Dado que as credenciais Cloudinary estão preenchidas no `.env`, quando uma imagem for gerada
  pelo pipeline, então ela deve ser hospedada com sucesso e retornar uma URL pública válida.
- Dado que as credenciais Cloudinary estão ausentes ou inválidas, quando o pipeline tentar
  hospedar uma imagem, então o erro deve ser registrado no histórico de erros do agente
  (tabela `errors`) e não deve travar o processo de forma silenciosa.

Regras de negócio relacionadas: RN-DEVOPS-01
Prioridade: **Alta** — sem isso, nenhuma imagem gerada pelo próprio agente pode ser publicada.
Dependências: nenhuma (pode rodar em paralelo a HU-DEVOPS-01).
Notas para o arquiteto/devs: nenhuma ação de código esperada; módulo `image_host.py` já existe.

---

## HU-DEVOPS-03: Configurar bot do Telegram para aprovação

Como **operador do agente**, quero **um bot do Telegram criado via @BotFather, com
`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` reais preenchidos no `.env`**, para que **eu consiga
revisar e aprovar/recusar/refazer posts antes da publicação**.

Critérios de Aceite:
- Dado que o token e o chat id estão configurados, quando `python -m src.main` for executado,
  então o bot deve subir sem erro e responder ao comando `/start`.
- Dado que apenas o `TELEGRAM_CHAT_ID` configurado tem permissão, quando outro chat tentar
  interagir com o bot, então a interação deve ser ignorada/rejeitada (regra já documentada no
  README do agente: "somente `TELEGRAM_CHAT_ID` autorizado pode interagir com o fluxo").

Regras de negócio relacionadas: RN-DEVOPS-01
Prioridade: **Alta** — bloqueia a aprovação humana, que é regra de negócio obrigatória do agente
(ver README do agente, seção "Regras de negócio", item 1).
Dependências: nenhuma.
Notas para o arquiteto/devs: nenhuma ação de código esperada.

---

## HU-DEVOPS-04: Validar o agente completo de ponta a ponta manualmente

Como **operador do agente**, quero **rodar `python -m src.main` e disparar `/force` no Telegram**,
para que **eu confirme que o fluxo completo (gerar → revisar → aprovar → publicar) funciona com
as credenciais reais antes de considerar o MVP destravado**.

Critérios de Aceite:
- Dado que HU-DEVOPS-01, HU-DEVOPS-02 e HU-DEVOPS-03 estão concluídas, quando o operador
  executar `/force` no Telegram e aprovar a prévia recebida, então o post deve ser publicado
  com sucesso (visível na fila do Buffer e, em seguida, no Instagram).
- Dado que o operador recusa a prévia, então o processo deve ser cancelado sem publicar
  (comportamento já existente, apenas confirmando que continua válido com credenciais reais).

Regras de negócio relacionadas: RN-AGENTE-01 (aprovação humana obrigatória, definida no README
do agente)
Prioridade: **Alta** — é o critério de "MVP destravado".
Dependências: HU-DEVOPS-01, HU-DEVOPS-02, HU-DEVOPS-03.
Notas para o arquiteto/devs: nenhuma ação de código esperada; é um teste de aceite manual do
operador, não uma entrega de dev.
