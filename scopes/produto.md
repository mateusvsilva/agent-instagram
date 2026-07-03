# Escopo: Produto — Agente impressam (visão geral, priorização e decisões)

> Fonte: `agents/impressam/TODO.md` (lido integralmente em 2026-06-16), cruzado com
> `agents/impressam/README.md` e `agents/impressam/COMO_RODAR.md`.
> Este arquivo é o guarda-chuva do plano. Os detalhes técnicos de cada item estão nos
> arquivos de escopo correspondentes (`devops.md`, `backend.md`, `frontend.md`, `conteudo-marca.md`).

## Objetivo de negócio

Colocar o Agente impressam operando de ponta a ponta — da definição do assunto do post até
a publicação aprovada no Instagram — reduzindo o trabalho manual de criação de conteúdo
recorrente, mantendo um humano no loop antes de qualquer publicação, e evoluindo o agente de
"executor de templates fixos" para "agente que pesquisa, escreve e ajusta com base em feedback".

## Contexto / Problema

O pipeline técnico básico (gerar imagem → aprovar no Telegram → publicar) já existe e parte dele
já funciona (publicação via Buffer testada). Mas o agente ainda não está no ar porque:
1. Faltam credenciais/contas de terceiros configuradas (bloqueio puro de configuração, não de
   desenvolvimento) — ver `devops.md`.
2. Faltam capacidades de "inteligência" que o TODO.md descreve como ainda não implementadas
   (pesquisa de mercado, legenda gerada por IA, pedido de assunto via Telegram, refazer com
   pergunta, leitura da pasta `prompts/`, briefing semanal no Hub) — ver `backend.md` e `frontend.md`.
3. Falta o conteúdo de identidade de marca que vai alimentar essas capacidades — ver `conteudo-marca.md`.

## Dentro do escopo (in scope) deste ciclo

- Destravar a configuração que já tem código pronto (Gemini, Cloudinary, Telegram).
- Evoluir o agente de "sorteia template" para "recebe assunto, pesquisa, escreve e gera imagem
  alinhado à marca".
- Loop de refação conversacional (perguntar o que mudar antes de refazer).
- Área de briefing semanal no Hub para guiar o agente com direção de conteúdo.
- Script de teste ponta a ponta sem depender do Telegram.
- Preenchimento do conteúdo de marca (`prompts/`).

## Fora do escopo (explicitamente, segundo o TODO.md)

- Vídeo/Reels (o agente é hoje focado em imagem e carrossel — confirmado no README do agente).
- Multi-cliente publicando nas próprias contas de Instagram via Buffer (Buffer hoje só serve
  contas que o operador controla; caminho futuro seria Graph API da Meta — mencionado no
  COMO_RODAR.md como decisão de longo prazo, **não faz parte deste backlog**).
- Modo "auto-publicar" sem aprovação humana — **não entra a menos que a decisão em aberto
  DA-02 seja resolvida nessa direção**. Hoje a aprovação humana é regra de negócio vigente
  (RN-AGENTE-01 no README do agente) e não há pedido explícito no TODO.md para revogá-la,
  apenas a pergunta em aberto.

## Premissas e dependências

- O pipeline de publicação (Buffer) e geração de imagem (Gemini) já tem código implementado;
  o que falta nessas frentes é configuração de credenciais, não desenvolvimento.
- As funcionalidades novas da Seção 2 do TODO.md têm ordem de dependência declarada pelo
  próprio documento ("em ordem de dependência. Cada uma é uma etapa do fluxo que você descreveu").
- O Hub (`hub/`) é o painel onde a "área de briefing semanal" deve viver, por ser o produto
  de controle central já existente.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Pesquisa de mercado sem fonte definida pode gerar conteúdo genérico ou incorreto | Tratado como ponto a validar (DA-03) antes de detalhar a história — ver `backend.md` |
| Geração de legenda por IA pode destoar do tom da marca | Depende de `prompts/` estar preenchido (`conteudo-marca.md`) antes de ativar a função |
| Item "auto-publicar" virar scope creep silencioso | Mantido fora de escopo até decisão explícita do usuário (DA-02) |
| Acúmulo de tentativas de refação em loop sem critério de parada visível ao usuário | Regra de negócio já existente no agente (`MAX_REDO_ATTEMPTS`) deve ser respeitada também no novo fluxo conversacional — ver RN-BACKEND-04 em `backend.md` |

## Métricas de sucesso

- Agente publica ao menos 1 post de ponta a ponta sem intervenção manual em infraestrutura
  (apenas aprovação via Telegram).
- Operador consegue pedir um assunto pelo Telegram e receber preview alinhado a esse assunto.
- Operador consegue registrar um briefing semanal no Hub e ver o agente refletir esse direcionamento
  nos posts da semana.
- Taxa de "refazer" com pergunta resolve a alteração pedida sem exceder `MAX_REDO_ATTEMPTS`.

---

## Backlog priorizado (MoSCoW)

A priorização segue a ordem de dependência que o próprio TODO.md já define ("ordem de cima para
baixo") combinada com valor de negócio (destravar o que já existe vem antes de construir
inteligência nova, que por sua vez vem antes de refinar qualidade de conteúdo).

### Must have (destrava o MVP — bloqueia tudo)
1. **DEVOPS-01** Ativar billing Gemini — ver `devops.md`
2. **DEVOPS-02** Criar conta e configurar Cloudinary — ver `devops.md`
3. **DEVOPS-03** Criar bot Telegram e configurar token/chat id — ver `devops.md`
4. **DEVOPS-04** Rodar o agente completo e validar fluxo manual (`/force` → aprovar) — ver `devops.md`

### Should have (capacidades novas, em ordem de dependência declarada no TODO)
5. **BACKEND-01** Pedido de assunto via Telegram — ver `backend.md`
6. **BACKEND-02** Pesquisa de mercado sobre o assunto — ver `backend.md`
7. **BACKEND-03** Legenda gerada por IA — ver `backend.md`
8. **BACKEND-04** Refazer com pergunta (loop conversacional) — ver `backend.md`
9. **BACKEND-05** Conectar pasta `prompts/` ao código — ver `backend.md`
10. **FRONTEND-01 / BACKEND-06** Briefing semanal no Hub — ver `frontend.md` e `backend.md`
11. **BACKEND-07** Script de teste ponta a ponta sem Telegram — ver `backend.md`

### Could have (paralelo, não bloqueia desenvolvimento)
12. **CONTEUDO-01 a 04** Preenchimento de identidade de marca, guidelines de imagem, caption e
    hashtag — ver `conteudo-marca.md` (pode rodar em paralelo às frentes técnicas, mas
    **BACKEND-03, BACKEND-05 e BACKEND-02 dependem desse conteúdo para ter qualidade real**).

### Won't have (fora deste ciclo)
- Modo auto-publicar sem Telegram (depende de decisão do usuário — DA-02).
- Suporte a múltiplos clientes publicando em contas próprias via Buffer/Graph API.
- Vídeo/Reels.

---

## Pontos em aberto / Decisões necessárias (DA)

Estes pontos vêm literalmente da seção "❓ Decisões suas" do TODO.md e de ambiguidades que
identifiquei ao detalhar as histórias. Nenhuma história que dependa deles foi especificada
com detalhe de comportamento até serem respondidos — apenas estruturadas com a pergunta em aberto.

- **DA-01 (Aprovação):** manter Telegram (recomendado pelo próprio TODO.md) ou adotar modo
  auto-publicar? Enquanto não for respondido, **RN-AGENTE-01 (aprovação humana obrigatória)
  permanece vigente e nenhuma história remove essa trava.**
- **DA-02 (Pesquisa de mercado):** de onde vem a pesquisa — busca na web aberta ou fontes
  específicas do nicho? Sem essa definição, BACKEND-02 não pode ser detalhado além do nível
  de história "preta" (o quê, sem o como nem as fontes).
- **DA-03 (Origem do assunto):** o assunto do post deve vir prioritariamente do briefing
  semanal no Hub, ou do pedido pontual no Telegram? O TODO.md sugere que ambos os canais devem
  existir, mas não define prioridade/desempate quando os dois estiverem ativos na mesma semana.
  Tratado como ponto a validar em BACKEND-01 e BACKEND-06.
- **DA-04 (Critério de aceite da pesquisa de mercado):** o TODO.md não define o que conta como
  "pesquisa de mercado" concluída (quantidade de fontes, formato de saída, nível de profundidade).
  Fica registrado como ponto a validar em BACKEND-02 — não inventei critério.
- **DA-05 (Formato do "guia" gerado pelo briefing semanal):** o TODO.md diz que o briefing
  "vira um guia no cérebro do agente", mas não especifica se isso é um arquivo em `prompts/`,
  um registro no banco do agente, ou outro mecanismo. Ponto a validar em BACKEND-06/FRONTEND-01.
