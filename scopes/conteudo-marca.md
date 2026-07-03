# Escopo: Conteúdo de Marca — Agente impressam

> Tarefas da Seção "🟡 3. Conteúdo da marca — VOCÊ" do `TODO.md`. Diferente dos demais escopos,
> estas tarefas não são de desenvolvimento — são insumo de produto/negócio que o próprio operador
> (usuário) preenche. Estão documentadas aqui como itens de backlog rastreáveis porque **bloqueiam
> a qualidade real** de HU-BACKEND-03 e HU-BACKEND-05 (`backend.md`): sem este conteúdo, a
> "conexão" do código com `prompts/` não tem o que refletir.

## Objetivo de negócio

Garantir que a identidade da marca impressam (público, tom, estilo visual, estratégia de
hashtag) esteja documentada de forma que o agente possa segui-la de verdade, em vez de operar
com scaffold vazio.

## Regras de negócio

- **RN-CONTEUDO-01**: Os arquivos em `prompts/` (`identity.md`, `image_guidelines.md`,
  `caption_guidelines.md`, `hashtag_strategy.md`) são a única fonte de identidade de marca que o
  agente deve consumir (uma vez que HU-BACKEND-05 estiver implementada) — não deve haver
  identidade de marca codificada em outro lugar do pipeline além desses arquivos.
- **RN-CONTEUDO-02**: Os marcadores `> PREENCHER:` presentes nesses arquivos indicam conteúdo
  pendente. Enquanto existirem, a regra RN-BACKEND-05 (comportamento de fallback ao ler `prompts/`
  incompletos) se aplica.

---

## HU-CONTEUDO-01: Preencher identidade da marca

Como **operador do agente**, quero **preencher `prompts/identity.md` com o que é a impressam,
seu público, objetivo e tom**, para que **o agente tenha uma base de identidade real para gerar
imagem e texto alinhados à marca**.

Critérios de Aceite:
- Dado o arquivo `prompts/identity.md`, quando o operador o preencher, então os marcadores
  `> PREENCHER:` devem ser substituídos por conteúdo real descrevendo a marca, público, objetivo
  e tom.

Regras de negócio relacionadas: RN-CONTEUDO-01, RN-CONTEUDO-02
Prioridade: **Alta** — é a base de identidade que as demais diretrizes (`image_guidelines.md`,
`caption_guidelines.md`) tendem a referenciar.
Dependências: nenhuma técnica; pode ser feito em paralelo a qualquer frente de desenvolvimento.
Notas para o arquiteto/devs: não há ação de código aqui; é insumo de conteúdo do operador.

---

## HU-CONTEUDO-02: Ajustar diretrizes visuais

Como **operador do agente**, quero **ajustar `prompts/image_guidelines.md` com estilo visual e
cores da marca**, para que **as imagens geradas pelo Gemini sigam um padrão visual consistente**.

Critérios de Aceite:
- Dado o arquivo `prompts/image_guidelines.md`, quando o operador o ajustar, então deve conter
  diretrizes claras de estilo visual e paleta de cores.

Regras de negócio relacionadas: RN-CONTEUDO-01, RN-CONTEUDO-02
Prioridade: **Alta** — pré-requisito de qualidade para HU-BACKEND-05.
Dependências: nenhuma técnica.
Notas para o arquiteto/devs: não há ação de código aqui.

---

## HU-CONTEUDO-03: Ajustar diretrizes de legenda e hashtag

Como **operador do agente**, quero **ajustar `prompts/caption_guidelines.md` e
`prompts/hashtag_strategy.md`**, para que **as legendas geradas por IA (HU-BACKEND-03) sigam o
tom certo e usem hashtags estrategicamente alinhadas ao nicho**.

Critérios de Aceite:
- Dado os arquivos `prompts/caption_guidelines.md` e `prompts/hashtag_strategy.md`, quando o
  operador os ajustar, então devem conter diretrizes claras de tom de voz e estratégia de
  hashtags.

Regras de negócio relacionadas: RN-CONTEUDO-01, RN-CONTEUDO-02
Prioridade: **Alta** — pré-requisito direto de HU-BACKEND-03 (legenda por IA) ter qualidade real.
Dependências: nenhuma técnica.
Notas para o arquiteto/devs: não há ação de código aqui.
