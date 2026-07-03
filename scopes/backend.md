# Escopo: Backend — Agente impressam (funcionalidades novas do pipeline)

> Tarefas da Seção "🟢 2. Funcionalidades novas" do `TODO.md`. O próprio documento declara que
> estão "em ordem de dependência" e que "cada uma é uma etapa do fluxo que você descreveu" — essa
> ordem foi preservada como prioridade relativa dentro deste escopo.
> Módulos hoje existentes e relevantes: `src/services/telegram_bot.py`,
> `src/handlers/approval_handler.py`, `src/handlers/command_handler.py`,
> `src/services/scheduler.py`, `src/services/post_composer.py`,
> `src/services/gemini_image_generator.py`. A pasta `prompts/` existe como scaffold mas
> ainda não é lida pelo código (confirmado no `COMO_RODAR.md`).

## Objetivo de negócio

Evoluir o agente de "sorteia um template fixo e publica" para "recebe ou define um assunto,
pesquisa sobre ele, escreve e ilustra de forma alinhada à marca, e aceita ajustes conversacionais
antes de publicar" — entregando o agente realmente "inteligente" descrito na visão do usuário.

## Regras de negócio

- **RN-BACKEND-01**: Hoje o `/force` apenas sorteia um template (comportamento atual, confirmado
  em `command_handler.py` e no TODO.md). Após esta frente, o operador deve poder também enviar um
  assunto livre pelo Telegram para iniciar a geração, sem remover a opção de sorteio existente.
- **RN-BACKEND-02**: A pesquisa de mercado deve ocorrer **antes** da geração de imagem e de
  legenda, alimentando ambas — é uma etapa do pipeline, não um recurso isolado e opcional.
  *(Ordem declarada no fluxo do `COMO_RODAR.md`: assunto → pesquisa → imagem → texto → revisão.)*
- **RN-BACKEND-03**: A legenda deixa de ser texto fixo de template e passa a ser gerada por IA,
  única por post, seguindo as diretrizes de marca (`prompts/caption_guidelines.md` e
  `prompts/hashtag_strategy.md`).
- **RN-BACKEND-04**: O fluxo de "Refazer" (🔄) deve perguntar ao operador o que alterar antes de
  regenerar, e isso deve operar em loop (pode repetir o ciclo perguntar→refazer→revisar) — mas
  **continua respeitando o limite `MAX_REDO_ATTEMPTS`** já existente como regra de negócio do
  agente (README, regra 6). Esta nova história não relaxa esse limite.
- **RN-BACKEND-04.1** (formalizada em 2026-06-18, ratifica comportamento já implementado em
  `main.py:_ask_redo_instruction`): a espera pela resposta do operador à pergunta de redo **deve**
  ter um tempo limite (não pode ser indefinida). Ao estourar, o agente **deve** regenerar o post
  sem instrução específica (fallback genérico) e essa tentativa **conta** para
  `MAX_REDO_ATTEMPTS` (não é uma tentativa "de graça"). **Lacuna identificada**: hoje o estouro
  só é logado, não notificado ao operador no Telegram — isso deve ser corrigido, pois o operador
  pode aprovar um post sem saber que o ajuste pedido não foi incorporado.
- **RN-BACKEND-04.2** (roteamento com múltiplos redos pendentes, já implementado em
  `conversation_handler.py`): com uma única pergunta de redo pendente, uma resposta sem reply
  explícito é aceita por conveniência. Com duas ou mais pendentes, a resposta **só** é roteada se
  vier como reply explícito à pergunta correta; caso contrário, o agente não regenera nada e
  orienta o operador a responder via reply — **a mensagem de orientação deve identificar quais
  posts estão pendentes** (não apenas dizer "responda à pergunta específica"), senão o operador
  não sabe qual reply fazer.
- **RN-BACKEND-04.3**: se um post é descartado (expirado ou rejeitado) enquanto há uma pergunta de
  redo pendente para ele, essa pergunta deve ser cancelada imediatamente. Uma resposta do operador
  que chegue depois não pode mais afetar esse post.
- **RN-BACKEND-04.4**: o conteúdo da instrução de redo não é validado quanto a clareza/qualidade —
  qualquer texto não vazio é aceito e usado na regeneração. O agente não deve pedir esclarecimento
  adicional sobre o conteúdo da instrução (apenas sobre o roteamento, ver RN-BACKEND-04.2).
- **RN-BACKEND-05**: A partir da conexão da pasta `prompts/` ao código, a identidade de marca
  (`identity.md`, `image_guidelines.md`, `caption_guidelines.md`, `hashtag_strategy.md`) deve
  guiar tanto o prompt de geração de imagem quanto o de geração de texto — deixando de ser apenas
  scaffold.
- **RN-BACKEND-06**: O briefing semanal registrado no Hub deve influenciar a escolha/definição de
  assunto dos posts daquela semana. *(O mecanismo exato de como o "guia" é armazenado e consumido
  é ponto a validar — DA-05 em `produto.md`. Esta regra define o efeito esperado, não a
  implementação.)*
- **RN-BACKEND-07**: O script de teste ponta a ponta deve cobrir Gemini → Cloudinary → Buffer
  **sem depender do Telegram**, conforme pedido explícito no TODO.md, para permitir validação
  rápida sem precisar de aprovação manual a cada teste.

## Casos de borda e exceções identificados

- O que acontece se o operador pedir um assunto pelo Telegram **e** existir um briefing semanal
  ativo no Hub na mesma semana? O TODO.md não resolve esse conflito de prioridade — registrado
  como **DA-03** em `produto.md`. Nenhuma história abaixo assume uma resposta para isso.
- O que conta como pesquisa de mercado "suficiente" (quantas fontes, que profundidade, que
  formato de saída) não está definido no TODO.md — registrado como **DA-04** em `produto.md`.
- De onde vem a pesquisa (web aberta vs. fontes do nicho) é uma decisão explicitamente pendente
  do próprio usuário no TODO.md (seção "❓ Decisões suas") — registrada como **DA-02**.

---

## HU-BACKEND-01: Pedido de assunto via Telegram

Como **operador do agente**, quero **enviar uma mensagem no Telegram pedindo "poste sobre X"**,
para que **o agente inicie a geração de um post sobre esse assunto específico, em vez de sortear
um template aleatório**.

Critérios de Aceite:
- Dado que o operador autorizado envia uma mensagem com um assunto, quando o agente recebe essa
  mensagem, então deve iniciar o pipeline de geração usando esse assunto como entrada (não como
  sorteio de template).
- Dado que o operador usa `/force` sem especificar assunto, quando o comando for executado, então
  o comportamento atual (sorteio de template) deve continuar funcionando — esta história não
  remove a opção existente.
- Dado que uma mensagem de assunto chega de um chat não autorizado, quando o agente processá-la,
  então deve ser ignorada (mesma regra de autorização já vigente para os demais comandos).

Regras de negócio relacionadas: RN-BACKEND-01
Prioridade: **Alta** — é a primeira etapa da cadeia de dependência declarada no TODO.md para
a Seção 2.
Dependências: nenhuma das demais histórias desta seção; é o ponto de entrada do fluxo novo.
Notas para o arquiteto/devs: avaliar como diferenciar "comando" de "mensagem de texto livre" no
bot do Telegram; ponto de atenção de UX conversacional, não prescrevo a solução técnica.

---

## HU-BACKEND-02: Pesquisa de mercado sobre o assunto

Como **operador do agente**, quero **que o agente pesquise sobre o assunto do post antes de criar
o conteúdo**, para que **o post seja mais relevante e embasado do que um template genérico**.

Critérios de Aceite:
- Dado um assunto definido (via Telegram ou via briefing semanal), quando o pipeline avançar para
  a etapa de pesquisa, então o resultado da pesquisa deve estar disponível para as etapas
  seguintes de geração de imagem e de legenda.
- Dado que a pesquisa falha ou não retorna resultado, então o pipeline deve registrar o erro
  (tabela `errors`) e **não pode** seguir silenciosamente como se a pesquisa tivesse sido feita.

Regras de negócio relacionadas: RN-BACKEND-02
Prioridade: **Alta** — segunda etapa da cadeia de dependência do TODO.md.
Dependências: HU-BACKEND-01 (precisa de um assunto definido para pesquisar sobre algo).
Notas para o arquiteto/devs: a fonte da pesquisa (web aberta vs. fontes específicas do nicho) é
decisão pendente do usuário (DA-02 em `produto.md`) — **não iniciar a implementação da fonte de
dados sem essa resposta**; o contrato de entrada/saída da etapa pode ser desenhado desde já.

---

## HU-BACKEND-03: Legenda gerada por IA

Como **operador do agente**, quero **que a legenda de cada post seja escrita por IA de forma
única, seguindo o tom da marca**, para que **eu não dependa de legendas fixas e repetitivas de
template**.

Critérios de Aceite:
- Dado que um post está sendo composto, quando a etapa de legenda for executada, então o texto
  gerado deve ser único para aquele post (não reaproveitar literalmente a `caption_template` fixa
  do template JSON).
- Dado que `prompts/caption_guidelines.md` e `prompts/hashtag_strategy.md` estão preenchidos,
  quando a legenda for gerada, então ela deve seguir essas diretrizes (depende de
  HU-BACKEND-05 e do conteúdo de `conteudo-marca.md`).
- Dado que a pesquisa de mercado (HU-BACKEND-02) retornou contexto sobre o assunto, quando a
  legenda for gerada, então esse contexto deve poder influenciar o texto.

Regras de negócio relacionadas: RN-BACKEND-03, RN-BACKEND-05
Prioridade: **Alta** — terceira etapa da cadeia de dependência do TODO.md.
Dependências: HU-BACKEND-02 (contexto da pesquisa), HU-BACKEND-05 (leitura de `prompts/`).
Notas para o arquiteto/devs: módulo `post_composer.py` hoje monta a caption a partir do template;
avaliar onde a geração por IA se encaixa nesse fluxo.

---

## HU-BACKEND-04: Refazer com pergunta (loop conversacional)

Como **operador do agente**, quero **que ao clicar 🔄 (Refazer) o agente me pergunte o que devo
alterar**, para que **a regeneração seja direcionada e eu não precise aceitar um resultado
genérico de novo sorteio**.

Critérios de Aceite:
- Dado que o operador clica 🔄 em uma prévia, quando o agente processar essa ação, então deve
  enviar uma pergunta ao operador pedindo o que deve ser alterado, antes de gerar qualquer coisa
  nova.
- Dado que o operador responde com a alteração desejada, quando o agente processar essa resposta,
  então deve regenerar o post incorporando esse pedido e reenviar para revisão.
- Dado que o operador clica 🔄 novamente sobre o novo resultado, então o ciclo
  pergunta→refazer→revisão deve poder se repetir.
- Dado que o número de tentativas de refação atinge `MAX_REDO_ATTEMPTS`, quando o operador tentar
  refazer novamente, então o post deve ser descartado e o operador notificado — **idêntico ao
  comportamento já documentado como regra de negócio existente** (README do agente, regra 6).
- Dado que existem duas ou mais perguntas de redo pendentes simultaneamente, quando o operador
  responde com reply explícito a uma delas, então apenas o post correspondente é regenerado.
- Dado que existem duas ou mais perguntas de redo pendentes simultaneamente, quando o operador
  responde sem reply a nenhuma pergunta específica, então nenhum post é regenerado e o operador
  recebe uma mensagem identificando quais posts estão pendentes, orientando-o a responder via
  reply.
- Dado que existe exatamente uma pergunta de redo pendente, quando o operador responde sem usar
  reply, então a instrução é aplicada a esse único post pendente (atalho de conveniência).
- Dado que o operador não responde à pergunta de redo dentro do tempo limite configurado, quando
  o tempo se esgota, então o post é regenerado sem instrução específica, essa tentativa conta para
  `MAX_REDO_ATTEMPTS`, e o operador é notificado no Telegram de que a regeneração ocorreu sem
  instrução por falta de resposta a tempo.
- Dado que um post é descartado (expiração ou rejeição) enquanto aguarda resposta de redo, quando
  esse descarte ocorre, então a pergunta pendente é cancelada e uma resposta tardia do operador
  não deve mais surtir efeito sobre esse post.

Regras de negócio relacionadas: RN-BACKEND-04, RN-BACKEND-04.1, RN-BACKEND-04.2, RN-BACKEND-04.3,
RN-BACKEND-04.4
Prioridade: **Alta** — quarta etapa da cadeia de dependência do TODO.md.
Dependências: nenhuma das histórias acima estritamente, mas se beneficia de HU-BACKEND-03 (para
poder ajustar legenda) e da geração de imagem já existente.
Notas para o arquiteto/devs: `approval_handler.py` já trata a ação de refazer; o ponto de atenção
é introduzir um estado conversacional intermediário (aguardando resposta do operador) antes de
disparar a regeneração. **Pontos a confirmar com o arquiteto** (ver DA-09 a DA-12 em
`produto.md`): (1) se o timeout de redo deve ter configuração própria, separada do timeout de
aprovação geral; (2) se os botões de aprovação do post original continuam ativos durante a espera
da resposta de redo (decide se falta um caminho de cancelamento explícito); (3) confirmar que a
notificação de timeout estourado (item acima) ainda não existe no código e precisa ser
adicionada.

---

## HU-BACKEND-05: Conectar a pasta `prompts/` ao código

Como **operador do agente**, quero **que a identidade de marca definida em `prompts/` realmente
guie a geração de imagem e de texto**, para que **o conteúdo passe a refletir a marca impressam de
verdade, e não apenas placeholders de template**.

Critérios de Aceite:
- Dado que `prompts/identity.md`, `prompts/image_guidelines.md`, `prompts/caption_guidelines.md`
  e `prompts/hashtag_strategy.md` estão preenchidos, quando uma imagem for gerada, então o prompt
  enviado ao Gemini deve incorporar as diretrizes de `image_guidelines.md` e `identity.md`.
- Dado os mesmos arquivos preenchidos, quando uma legenda for gerada (HU-BACKEND-03), então ela
  deve incorporar `caption_guidelines.md` e `hashtag_strategy.md`.
- Dado que algum arquivo de `prompts/` está vazio ou só com os marcadores `> PREENCHER:`, quando
  o pipeline rodar, então deve haver um comportamento previsível (ex.: aviso/log de que a
  identidade de marca está incompleta) — **o comportamento exato de fallback é ponto a validar**,
  pois o TODO.md não especifica o que fazer nesse caso.

Regras de negócio relacionadas: RN-BACKEND-05
Prioridade: **Alta** — é pré-requisito declarado para HU-BACKEND-03 funcionar com qualidade real,
e está na cadeia de dependência do TODO.md.
Dependências: depende do conteúdo estar preenchido (`conteudo-marca.md`) para ter valor prático,
mas a capacidade de leitura pode ser construída em paralelo.
Notas para o arquiteto/devs: nenhuma área do código hoje lê `prompts/` (confirmado via busca no
repositório) — é integração nova, não ajuste de algo existente.

---

## HU-BACKEND-06: Suporte de backend ao briefing semanal do Hub

Como **agente de geração de conteúdo**, quero **consumir o briefing semanal registrado pelo
operador no Hub**, para que **a definição do assunto dos posts da semana siga a direção que o
operador definiu, e não apenas pedidos pontuais ou sorteio**.

Critérios de Aceite:
- Dado que um briefing semanal foi registrado no Hub (ver HU-FRONTEND-01 em `frontend.md`),
  quando o agente for definir o assunto de um post programado por horário, então deve considerar
  esse briefing como direção preferencial.
- Dado que não existe briefing ativo para a semana corrente, quando o agente precisar definir
  assunto para um post agendado, então o comportamento deve cair para a lógica já existente
  (sorteio de template) — esta história não pode quebrar o fluxo atual na ausência de briefing.

Regras de negócio relacionadas: RN-BACKEND-06
Prioridade: **Média** — depende de uma definição de produto ainda não fechada (DA-05: formato do
"guia") e de existir a interface correspondente no Hub (FRONTEND-01).
Dependências: HU-FRONTEND-01 (é preciso existir um lugar para o briefing ser registrado antes de
o backend poder consumi-lo).
Notas para o arquiteto/devs: o formato de armazenamento do "guia" (arquivo em `prompts/`,
registro em banco, ou outro) é ponto a validar (DA-05 em `produto.md`) — não prescrevo aqui.

---

## HU-BACKEND-07: Script de teste ponta a ponta sem Telegram

Como **operador do agente**, quero **um script `test_end_to_end.py` que execute
Gemini → Cloudinary → Buffer sem depender do Telegram**, para que **eu valide rapidamente o
pipeline técnico sem precisar aprovar manualmente a cada teste**.

Critérios de Aceite:
- Dado que as credenciais de Gemini, Cloudinary e Buffer estão configuradas, quando o script for
  executado, então deve gerar uma imagem, hospedá-la e publicá-la (ou simular a publicação, a
  confirmar) sem exigir nenhuma interação no Telegram.
- Dado que qualquer uma das três etapas falhar, quando o script for executado, então deve indicar
  claramente em qual etapa ocorreu a falha (mesmo padrão de clareza já usado em
  `scripts/test_buffer.py` e `scripts/test_gemini.py`, citados no `COMO_RODAR.md`).

Regras de negócio relacionadas: RN-BACKEND-07
Prioridade: **Média** — é uma ferramenta de validação, não uma capacidade voltada ao usuário
final do produto, mas acelera a entrega de todo o resto.
Dependências: nenhuma estrita, mas só tem valor pleno depois de HU-DEVOPS-01 e HU-DEVOPS-02
(Gemini e Cloudinary configurados).
Notas para o arquiteto/devs: o TODO.md não especifica se este script deve de fato publicar no
Buffer real ou apenas simular até a fila — **ponto a validar**: confirmar com o operador se o
script pode gerar publicações reais de teste ou se deve ter um modo "dry-run".
