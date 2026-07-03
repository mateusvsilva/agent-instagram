# Escopo: Frontend — Agente impressam (Hub)

> Tarefa originada do item "Briefing semanal no Hub" da Seção "🟢 2. Funcionalidades novas" do
> `TODO.md`. É a única tarefa do TODO.md com componente claro de interface — as demais da Seção 2
> são lógica de pipeline (ver `backend.md`).
> O Hub hoje (`hub/web/index.html`, `styles.css`, `app.js`) não possui nenhuma área de
> conversa/briefing — confirmado por leitura da estrutura atual do projeto. Esta é uma capacidade
> nova de interface, não um ajuste de tela existente.

## Objetivo de negócio

Dar ao operador um lugar único, dentro do painel que ele já usa para administrar o agente
(o Hub), para declarar a direção de conteúdo da semana — substituindo a necessidade de pedir
assunto por assunto manualmente pelo Telegram a cada post.

## Regras de negócio

- **RN-FRONTEND-01**: A área de briefing semanal deve ficar acessível a partir do papel
  **administrador** do Hub. *(O TODO.md não diz se o papel cliente também deve ter acesso —
  ver ponto a validar abaixo. Pelo modelo de permissões hoje documentado no README do Hub, o
  cliente só pode editar templates do próprio agente e ver consumo; histórico de operação e
  decisões de conteúdo de mais alto nível tendem a ser função do administrador, mas isso não
  está confirmado para este recurso específico.)*
- **RN-FRONTEND-02**: O briefing registrado deve ser associável a uma janela de tempo
  ("essa semana, a partir do dia tal") — não é um campo de texto solto sem data de vigência,
  conforme descrito no `COMO_RODAR.md` ("essa semana, a partir do dia tal, quero postar sobre
  tal assunto").

## Casos de borda e exceções identificados

- Não está definido no TODO.md se o briefing pode ser editado/substituído depois de registrado,
  ou se é só leitura após criado. **Ponto a validar.**
- Não está definido se pode haver mais de um briefing ativo simultaneamente (ex.: briefings para
  semanas futuras registrados com antecedência) ou só um briefing "corrente" por vez.
  **Ponto a validar.**

---

## HU-FRONTEND-01: Área de briefing semanal no Hub

Como **administrador do agente**, quero **uma área no Hub onde eu converse com a IA e diga
"essa semana, a partir do dia X, quero postar sobre Y"**, para que **essa direção vire um guia que
influencia os posts gerados pelo agente naquela semana, sem eu precisar pedir assunto por
assunto no Telegram**.

Critérios de Aceite:
- Dado que o administrador está autenticado no Hub, quando ele acessar a área de briefing,
  então deve conseguir registrar um assunto/direção de conteúdo associado a um período de
  vigência (data de início, ao menos).
- Dado que um briefing foi registrado, quando o agente correspondente buscar direção de conteúdo
  para a semana (ver HU-BACKEND-06 em `backend.md`), então o briefing registrado deve estar
  disponível para consulta por esse agente.
- Dado que o administrador está vendo a área de briefing, quando ele alternar entre agentes
  (capacidade já existente no Hub), então o briefing exibido/editável deve ser o do agente
  selecionado — **não pode misturar briefings de agentes diferentes**, seguindo o mesmo princípio
  de isolamento por agente que já rege o restante do Hub (README do Hub, seção "Perfis de
  acesso").

Regras de negócio relacionadas: RN-FRONTEND-01, RN-FRONTEND-02
Prioridade: **Média** — depende de uma decisão de produto ainda aberta (DA-05, formato do "guia"
gerado) antes de poder ser detalhada para implementação; o valor é alto, mas não é a primeira
prioridade da Seção 2 segundo a ordem de dependência do próprio TODO.md (vem depois das
capacidades de pesquisa/legenda/refazer).
Dependências: nenhuma tecnicamente bloqueante para começar o desenho de tela, mas a integração
fim a fim depende de HU-BACKEND-06.
Notas para o arquiteto/devs: o TODO.md descreve esta área como "conversar com a IA" — não está
claro se isso significa um chat interativo de fato ou um formulário estruturado (assunto +
data) que é apenas apresentado como "conversa". **Ponto a validar com o usuário antes do desenho
de interface**, para não construir uma experiência mais complexa (chat) do que o necessário se a
intenção real for um formulário simples.

---

## Pontos em aberto / Decisões necessárias (específicos deste escopo)

- Papel com acesso (admin apenas, ou também cliente) — RN-FRONTEND-01.
- Edição/substituição de briefing já registrado — sim ou não, e como.
- Um briefing ativo por vez vs. múltiplos briefings futuros agendados.
- Natureza da interface: chat conversacional real vs. formulário estruturado apresentado como
  conversa (impacta diretamente o esforço de implementação — por isso fica registrado aqui em
  vez de assumido).
