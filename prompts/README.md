# Prompts — o "cérebro" do agente impressam

Esta pasta concentra a **engenharia de prompt** do agente: quem ele é, como cria
imagens e como escreve legendas. É a fonte única de verdade da marca. Os
`data/templates/*.json` continuam definindo **temas específicos** (paisagem,
café, etc.); os arquivos daqui definem o **padrão que vale para todos os temas**.

## Camadas (ordem de leitura)

1. **`identity.md`** — base compartilhada. Quem é o agente, o que é a impressam,
   missão, público, tom geral, limites. É injetado em TUDO.
2. **`image_guidelines.md`** — regras e padrões de criação de imagem.
3. **`caption_guidelines.md`** — como escrever o título/legenda do post.
4. **`hashtag_strategy.md`** — estratégia de hashtags.

## Como o agente monta cada geração

```
IMAGEM   = identity.md  +  image_guidelines.md  +  prompt do template (tema)
LEGENDA  = identity.md  +  caption_guidelines.md +  contexto do post
HASHTAGS = hashtag_strategy.md  +  pool do template
```

Ou seja: a marca (identity) é a base; cada arquivo de "guidelines" adiciona as
regras do seu trabalho; o template entra com o tema do dia.

## Como editar

- São arquivos **Markdown** — escreva em linguagem natural, como um manual.
- Seja específico e dê exemplos (o modelo segue melhor com exemplos).
- Onde estiver `> PREENCHER:` é um campo que precisa da sua resposta.
- Mudou a marca? Edite `identity.md` e pronto — vale para imagem e legenda.

## Status

Estrutura criada em 2026-06-15. A leitura desses arquivos pelo código
(`image_generator` / `post_composer`) é o próximo passo da implementação.
