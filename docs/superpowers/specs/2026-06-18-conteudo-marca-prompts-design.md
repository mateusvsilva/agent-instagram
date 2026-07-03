# Design — Conteúdo de marca e engenharia de prompt (impressam)

- **Data:** 2026-06-18
- **Origem:** sessão de brainstorming (escopo `scopes/conteudo-marca.md`, HU-CONTEUDO-01/02/03)
- **Status:** aprovado para virar plano de implementação

## 1. Contexto e objetivo

O pipeline do agente impressam já está implementado e **já consome** a pasta `prompts/`
e os `data/templates/*.json`. O que falta é o **conteúdo de marca real**: os 4 arquivos em
`prompts/` ainda estão cheios de marcadores `> PREENCHER:`, e os 2 templates existentes
(`abstract_minimalist`, `sunset_landscape`) são genéricos e **não têm relação** com o negócio.

Este design define o conteúdo final dos 4 arquivos de marca e um novo conjunto de templates
alinhados ao negócio: **impressão 3D para o setor industrial**, voltada a **autoridade técnica**.

O cliente é a **impressam** (Jundiaí/SP e região), que fabrica peças 3D sob demanda —
com foco em peças difíceis de achar / fora de linha: engrenagens, parafusos especiais,
componentes de máquinas de injeção de plástico, peças de torno/CNC, módulos. Resolve a dor
de "a peça quebrou, não acha no mercado, e a máquina está parada".

### Como o conteúdo entra no pipeline (verificado no código)

- `PromptsLoaderService.load()` lê os 4 arquivos → `BrandIdentity` (`src/services/prompts_loader.py`).
- **Imagem:** `main.py:360` injeta `BrandIdentity.image_brief()` = `identity.md` + `image_guidelines.md`,
  **verbatim**, antes do prompt do template (`src/services/gemini_image_generator.py::_build_prompt`).
- **Legenda:** `CaptionGeneratorService` usa `BrandIdentity.caption_brief()` =
  `identity.md` + `caption_guidelines.md` + `hashtag_strategy.md` (`src/services/caption_generator.py:82`).
- **Detecção de incompleto:** `prompts_loader._is_incomplete()` marca um arquivo como incompleto
  se estiver vazio **ou contiver `> PREENCHER:`**, e registra warning + degrada a qualidade.

**Implicação de design:** como `identity.md` + `image_guidelines.md` vão **verbatim** para o
modelo de imagem, esses dois arquivos devem ser **concisos e com vocabulário visual** — evitar
manifesto longo (missão, limites etc. extensos) que "suja" o prompt de imagem.

## 2. Decisões de design (tomadas na sessão)

| Decisão | Escolha | Efeito |
|---|---|---|
| Objetivo nº1 do perfil | **Autoridade técnica / reputação** | Conteúdo educativo/credibilidade; CTA suave (não venda dura). |
| Texto dentro da imagem | **IA escreve texto curto** | Revisa a regra "nunca texto"; libera templates de banner com texto curto. |
| Visual âncora | **Editorial de engenharia (studio limpo)** | Macro de peça, luz de estúdio, paleta neutra + acento, realismo. |
| Voz da legenda | **Especialista direto (mais técnico)** | Tom de engenheiro, vocabulário técnico, sem emoji. |

### Fatos da marca

- **Local / alcance:** Jundiaí/SP e região.
- **Canal de contato:** WhatsApp (CTA aponta pra ele).
- **Persona:** conta institucional **impressam**; **Samuel Grisotto (CEO)** como figura de
  autoridade citável em posts de bastidor/expertise.
- **Setores-alvo:** indústria mecânica, plástica e setor industrial em geral (manutenção/reposição).

### Lacunas em aberto (a confirmar com a impressam — não bloqueiam a implementação)

1. **Paleta/logo oficiais** — usamos acento provisório **azul técnico `#1B4D7E`** (alternativa:
   laranja industrial `#E8541E`). Trocar quando a marca definir.
2. **Materiais/processos exatos** (FDM, resina/SLA, SLS; PLA/PETG/ABS/Nylon/fibra de carbono) —
   até confirmar, as diretrizes falam de material de forma **genérica** (regra "não prometer
   material/tolerância não confirmado").
3. **Número/links de WhatsApp** — vivem na bio/post, não nas diretrizes.

### Convenção de placeholder (importante)

Os arquivos entregues **não** devem conter `> PREENCHER:` (dispara a degradação no
`prompts_loader`) **nem** notas meta (que iriam verbatim pro prompt). Onde um fato ainda é
desconhecido, escrevemos um **default confiável e genérico**; o rastreamento do que confirmar
fica **neste spec**, não nos arquivos. Resultado esperado: o loader loga "todas as seções
preenchidas".

## 3. Pilares de conteúdo (5)

1. **Peça em destaque** — close editorial de uma peça impressa. "O que fabricamos."
2. **Impressora em operação** — bastidor de produção; capacidade.
3. **Problema → solução** — peça fora de linha resolvida com 3D (caso/aplicação). Forte pra B2B.
4. **Educativo / técnico** — banner de texto curto (quando o 3D vale, materiais, tolerância,
   engenharia reversa). Constrói autoridade.
5. **Bastidor / autoridade** — Samuel Grisotto e a operação; "por que confiar". Ocasional.

Cada pilar vira um template (Seção 5).

## 4. Conteúdo proposto dos arquivos `prompts/`

### 4.1 `prompts/identity.md`

```markdown
# Identidade do agente

> Base compartilhada. Tudo (imagem e legenda) é construído sobre este arquivo.
> Mantê-lo conciso: este texto entra verbatim também no prompt de imagem.

## Quem é o agente
- **Persona:** conta institucional — assina como **impressam** (sem nome-fantasia). Voz de especialista técnico.
- **Papel:** social media autônomo da impressam no Instagram — cria e publica conteúdo visual com aprovação humana.
- **Figura de autoridade:** Samuel Grisotto (CEO) — citável em posts de bastidor e expertise.

## Sobre a impressam (o cliente)
- **O que faz:** impressão 3D para o setor industrial, em Jundiaí/SP e região. Fabrica peças sob demanda, com foco no que é difícil de achar ou está fora de linha.
- **O que oferece:** peças industriais em 3D — engrenagens, parafusos especiais, buchas, componentes de máquinas de injeção de plástico, peças de torno/CNC, módulos e protótipos; engenharia reversa de componentes descontinuados.
- **Diferencial:** precisão e agilidade na reposição de peças difíceis; resolve parada de máquina quando a peça não existe mais no mercado ou demora a importar; atendimento por quem fala a língua da indústria mecânica e plástica.
- **Contato:** WhatsApp (canal principal).

## Missão no Instagram
Construir autoridade técnica e reputação como referência em impressão 3D industrial em Jundiaí e região: mostrar capacidade, educar sobre quando o 3D resolve e gerar confiança que leva ao contato no WhatsApp (CTA suave, sem venda dura).

## Público-alvo
- **Quem:** profissionais da indústria, 40+, decisores técnicos (manutenção, engenharia, donos de fábrica, comprador técnico) que lidam com parada de máquina e reposição de peças.
- **O que valoriza:** precisão, prazo, confiabilidade, resolver sem parar a produção; desconfia de promessa exagerada.

## Tom (visão geral)
Técnico · preciso · confiável · direto · especialista.

## Pilares de conteúdo
1. Peça em destaque  2. Impressora em operação  3. Problema → solução  4. Educativo/técnico  5. Bastidor/autoridade.

## Limites — o que o agente NUNCA faz
- Não promete o que a impressam não entrega (incl. material/tolerância/prazo não confirmados).
- Não cita cliente ou marca de terceiro sem permissão; não inventa dado técnico.
- Não usa conteúdo ofensivo, político ou sensível.
```

### 4.2 `prompts/image_guidelines.md`

```markdown
# Diretrizes de criação de imagem

> Regras que valem para TODA imagem. Combinado com `identity.md` e o prompt do template,
> forma o prompt final. Escrever com vocabulário visual e conciso.

## Estética da marca
- **Estilo:** fotográfico realista, editorial de engenharia, studio limpo ("industrial product photography", "editorial"). Nunca render CGI ou plástico de brinquedo.
- **Sensação:** precisão, qualidade, confiabilidade, premium técnico.

## Paleta
- Neutros (branco, cinza concreto, aço escovado, grafite) + 1 acento: azul técnico profundo (#1B4D7E).
- Evitar: tons saturados/infantis, neon excessivo, fundos coloridos poluídos.

## Composição e enquadramento
- Formato retrato 4:5 (já em `GEMINI_ASPECT_RATIO`).
- Assunto principal nítido (a peça), profundidade de campo rasa, respiro nas bordas, sem poluição.
- Macro/close para peças; plano médio para a impressora em operação; flat lay para conjunto de peças.

## Iluminação
- Luz de estúdio suave e direcional (realista). Em chão de fábrica, luz mais natural/dura, ainda realista.

## Texto na imagem
- ✅ Permitido texto curto (título, dado ou rótulo): poucas palavras, fonte legível, alto contraste. Banner = no máximo 1 frase + 1 dado.
- ❌ Parágrafos ou blocos longos (o modelo erra letras).

## Elementos recorrentes
- Cor de acento presente de forma sutil.
- Logo/marca d'água discreta no canto quando houver arquivo de logo.

## Proibições (hard "never")
- ❌ Texto longo na imagem.   ❌ Logos/marcas de terceiros.
- ❌ Peça com cara de brinquedo / plástico barato.
- ❌ Anatomia humana estranha (mãos, dedos, rostos distorcidos).
- ❌ Aparência de render CGI fake — buscar sempre realismo fotográfico.
- ❌ Conteúdo sensível, violento ou contra as regras do Instagram.

## Padrão técnico
- Alta resolução, nitidez, qualidade profissional ("industrial product photography", "editorial", "high detail", "sharp focus", "professional lighting").
- Aspect ratio 4:5.

## Montagem do prompt final
[diretrizes de marca] + [tema do template] + [padrão técnico]
Ex.: "Macro product shot of a precision 3D-printed gear on brushed steel, soft directional studio light, shallow depth of field, neutral palette with subtle blue accent — industrial editorial photography, high detail, 4:5."
```

### 4.3 `prompts/caption_guidelines.md`

```markdown
# Diretrizes de legenda (título + texto do post)

> Como o agente escreve a legenda. Combinado com `identity.md`, define a voz. Idioma: pt-BR.

## Estrutura do post
1. **Gancho (1ª linha):** problema concreto ou afirmação técnica — não clickbait. Ex.: "Engrenagem fora de linha parando a injetora?"
2. **Corpo (2-4 linhas):** desenvolve com benefício/dado técnico — precisão, material, prazo, engenharia reversa.
3. **CTA:** suave e variável, sempre apontando para o WhatsApp. Ex.: "Tem uma peça que ninguém mais fabrica? Chama no WhatsApp." / "Salve para quando precisar." / "Manda a peça que a gente avalia."

## Voz e tom
- Especialista direto, institucional ("nós / a impressam"), trata o leitor por "você".
- Vocabulário técnico (tolerância, material, prototipagem, engenharia reversa) com naturalidade, sem arrogância.
- Pode atribuir/assinar a Samuel Grisotto em posts de autoridade/bastidor.

## Tamanho
- Curto e escaneável (3 a 6 linhas). Educativos podem esticar um pouco quando o tema pedir.

## Emojis
- Zero a mínimo — no máximo 1 emoji funcional por post, e só quando agregar. Público sênior/industrial: sobriedade.

## Hashtags
- Geradas pela `hashtag_strategy.md`, ao final (ou no 1º comentário).

## O que evitar
- ❌ Clickbait ou promessa falsa.   ❌ Prometer material/tolerância/prazo não confirmado.
- ❌ Emoji em excesso; tom "marketeiro" leve demais.
- ❌ Erro de português; texto genérico que serve para qualquer marca.
- ❌ Repetir sempre a mesma abertura/CTA.

## Exemplos
- **Bom:**
  "Reposição de peça fora de linha.
  Componente descontinuado, injetora parada. Modelamos por engenharia reversa e imprimimos em material de engenharia compatível, com a tolerância exigida — máquina de volta à produção.
  Tem uma peça que ninguém mais fabrica? Chama no WhatsApp."
- **Ruim (não fazer):**
  "🚀🔥 A IMPRESSÃO 3D VAI MUDAR SUA VIDA!!! Clica já e surpreenda-se ✨✨"
```

### 4.4 `prompts/hashtag_strategy.md`

```markdown
# Estratégia de hashtags

> Como o agente escolhe hashtags. Combinado com o `hashtag_pool` de cada template.

## Mix recomendado (total ≈ 15-20)
- **Marca (fixas):** #impressam #impressao3d
- **Nicho:** #impressao3dindustrial #manufaturaaditiva #engenhariareversa #pecassobdemanda #prototipagem #fdm
- **Setores:** #injecaodeplastico #usinagem #cnc #industriamecanica #manutencaoindustrial
- **Amplas:** #industria #engenharia #fabricacao
- **Locais:** #jundiai #jundiairegiao #interiorsp #industriasp

## Regras
- 15-20 por post. Variar entre posts (não repetir o mesmo bloco). Coerentes com imagem e legenda.

## Proibidas
- ❌ Hashtags banidas/shadowban do Instagram.   ❌ Hashtags enganosas (sem relação com o post).
- ❌ Hashtags de "arte gerada por IA" (#aiart, #dalleai, #generativeart, #aiartwork) — minam a credibilidade técnica e o posicionamento de autoridade.
```

## 5. Templates (`data/templates/`)

**Remover** `abstract_minimalist.json` e `sunset_landscape.json`. **Criar** 5 templates (1 por pilar).
Prompts em inglês (o modelo segue melhor), legenda/hashtag em pt-BR. `dalle_params` em retrato
(`1024x1792`, `quality: hd`, `style: natural` — "natural" favorece o realismo industrial).

> **Texto de banner sem acento, de propósito:** os `headline`/`title` dos templates de banner
> usam CAIXA ALTA **sem acento** (ex.: "PECA FORA DE LINHA?") porque os modelos de imagem
> renderizam mal caracteres acentuados (ç, ã, é). Não é erro de digitação. A legenda (texto fora
> da imagem) usa acentuação normal de pt-BR.

### 5.1 `peca_destaque.json`
```json
{
  "id": "peca_destaque",
  "name": "Peça em Destaque",
  "prompt": "Macro product shot of a precision 3D-printed {part}, {material_look}, resting on {surface}, soft directional studio lighting, shallow depth of field, neutral palette with a subtle blue accent, industrial editorial product photography, ultra sharp focus, high detail, photorealistic, no toy-like plastic look",
  "variables": {
    "part": ["mechanical gear", "custom threaded screw", "bushing", "mounting bracket", "shaft coupling", "injection-mold insert"],
    "material_look": ["matte black PETG", "grey engineering nylon", "carbon-fiber-filled black", "matte technical resin"],
    "surface": ["brushed steel", "light concrete", "dark graphite surface"]
  },
  "caption_template": "Peça impressa sob medida.\n\nProjetada e fabricada em 3D para encaixe e função exatos. Tem uma peça difícil de achar? Chama no WhatsApp.",
  "hashtag_pool": ["#impressam", "#impressao3d", "#pecassobdemanda", "#manufaturaaditiva", "#pecas3d", "#fdm", "#prototipagem", "#industriamecanica", "#usinagem", "#injecaodeplastico", "#industria", "#engenharia", "#fabricacao", "#jundiai", "#jundiairegiao", "#interiorsp"],
  "image_count": 3,
  "dalle_params": {"size": "1024x1792", "quality": "hd", "style": "natural"},
  "active": true
}
```

### 5.2 `impressora_trabalhando.json`
```json
{
  "id": "impressora_trabalhando",
  "name": "Impressora em Operação",
  "prompt": "A modern industrial FDM 3D printer in operation, printing a mechanical part on the build plate, {environment}, realistic lighting, shallow depth of field, professional industrial photography, high detail, photorealistic",
  "variables": {
    "environment": ["clean engineering workshop", "factory floor with CNC machines softly blurred in the background", "industrial 3D printing lab"]
  },
  "caption_template": "Produção em andamento.\n\nCada peça nasce de um modelo 3D e é impressa com precisão — da ideia à peça pronta, sem depender de estoque de fabricante.",
  "hashtag_pool": ["#impressam", "#impressao3d", "#manufaturaaditiva", "#fdm", "#prototipagem", "#impressao3dindustrial", "#pecas3d", "#industria", "#engenharia", "#fabricacao", "#manufatura", "#industria40", "#manutencaoindustrial", "#jundiai", "#jundiairegiao", "#industriasp"],
  "image_count": 3,
  "dalle_params": {"size": "1024x1792", "quality": "hd", "style": "natural"},
  "active": true
}
```

### 5.3 `problema_solucao.json`
```json
{
  "id": "problema_solucao",
  "name": "Problema para Solução",
  "prompt": "Industrial editorial photo, side-by-side composition: on the left a worn and broken machine part, on the right the freshly 3D-printed replacement, clean studio lighting, neutral background with a subtle blue accent, short bold overlay text \"{headline}\", high detail, photorealistic, short text only",
  "variables": {
    "headline": ["FORA DE LINHA? A GENTE IMPRIME", "PECA QUEBROU. RESOLVIDO.", "SEM ESTOQUE? SEM PROBLEMA"]
  },
  "caption_template": "Peça fora de linha não precisa parar sua máquina.\n\nReproduzimos o componente por engenharia reversa e imprimimos em 3D. Manda a peça que a gente avalia no WhatsApp.",
  "hashtag_pool": ["#impressam", "#impressao3d", "#engenhariareversa", "#pecassobdemanda", "#impressao3dindustrial", "#manutencaoindustrial", "#industriamecanica", "#injecaodeplastico", "#usinagem", "#manufaturaaditiva", "#industria", "#engenharia", "#fabricacao", "#jundiai", "#jundiairegiao", "#interiorsp"],
  "image_count": 2,
  "dalle_params": {"size": "1024x1792", "quality": "hd", "style": "natural"},
  "active": true
}
```

### 5.4 `educativo_tecnico.json`
```json
{
  "id": "educativo_tecnico",
  "name": "Banner Tecnico",
  "prompt": "Clean minimal industrial banner, a single 3D-printed {part} on a neutral background, generous negative space, short bold title text \"{title}\", subtle blue accent, editorial industrial photography, high detail, photorealistic, short text only",
  "variables": {
    "part": ["gear", "bracket", "custom part"],
    "title": ["QUANDO VALE IMPRIMIR EM 3D", "ENGENHARIA REVERSA", "FDM x RESINA", "PECA FORA DE LINHA?"]
  },
  "caption_template": "Impressão 3D não é sobre protótipo bonito — é sobre resolver.\n\nQuando a peça é difícil de achar, foi descontinuada ou precisa de ajuste fino, o 3D entrega no prazo. Salve este post para quando precisar.",
  "hashtag_pool": ["#impressam", "#impressao3d", "#impressao3dindustrial", "#manufaturaaditiva", "#engenhariareversa", "#prototipagem", "#fdm", "#usinagem", "#industria", "#engenharia", "#fabricacao", "#manufatura", "#industria40", "#jundiai", "#jundiairegiao", "#interiorsp"],
  "image_count": 2,
  "dalle_params": {"size": "1024x1792", "quality": "hd", "style": "natural"},
  "active": true
}
```

### 5.5 `bastidor_autoridade.json`
```json
{
  "id": "bastidor_autoridade",
  "name": "Bastidor e Autoridade",
  "prompt": "Behind-the-scenes of an industrial 3D printing workshop, finished printed parts on a workbench, hands inspecting a part (no visible face), machines softly blurred in the background, realistic documentary lighting, professional photography, high detail, photorealistic",
  "variables": {},
  "caption_template": "Por trás de cada peça: processo e controle.\n\nNa impressam, cada componente é avaliado antes de chegar à sua máquina. Precisão não é detalhe — é o serviço.",
  "hashtag_pool": ["#impressam", "#impressao3d", "#impressao3dindustrial", "#manufaturaaditiva", "#pecassobdemanda", "#industriamecanica", "#ferramentaria", "#prototipagem", "#fdm", "#industria", "#engenharia", "#fabricacao", "#jundiai", "#jundiairegiao", "#interiorsp", "#industriasp"],
  "image_count": 2,
  "dalle_params": {"size": "1024x1792", "quality": "hd", "style": "natural"},
  "active": true
}
```

> Nota (`bastidor_autoridade`): não inventar o rosto do Samuel — o prompt foca ambiente/mãos/peças.
> Quando houver foto real do CEO, usar via `/force` ou um fluxo de imagem real (fora deste escopo).

## 6. Mudanças necessárias

**Conteúdo (núcleo deste design):**
1. Substituir o conteúdo dos 4 arquivos em `prompts/` pelos da Seção 4 (zero `> PREENCHER:` restante).
2. Criar os 5 templates da Seção 5 em `data/templates/`.
3. Remover `data/templates/abstract_minimalist.json` e `data/templates/sunset_landscape.json`.

**Código:** nenhuma mudança estrutural — o pipeline já consome `prompts/` e os templates.
- Verificar apenas que, com `IMAGE_PROVIDER=openai` (DALL-E ativo hoje), os prompts com texto
  ("short text only" / `{headline}`/`{title}`) ainda produzam bom resultado; o DALL-E erra mais
  texto que o Gemini (Nano Banana). Recomendação: ao gerar banners (`problema_solucao`,
  `educativo_tecnico`), preferir `IMAGE_PROVIDER=gemini` quando o billing do Gemini estiver ativo.

## 7. Fora de escopo

- Mudanças no pipeline/portas (já implementadas).
- Geração/curadoria real de imagens (acontece depois, via pipeline; pode-se rodar testes via `/force`).
- Logo/identidade visual gráfica oficial; número de WhatsApp; lista exata de materiais (lacunas §2).
- Configuração de billing do Gemini / chaves (`scopes/devops.md`).

## 8. Critérios de aceite

- **HU-CONTEUDO-01:** `prompts/identity.md` descreve marca, público, missão e tom reais; sem `> PREENCHER:`.
- **HU-CONTEUDO-02:** `prompts/image_guidelines.md` traz estilo visual, paleta e regra de texto-na-imagem revisada; sem `> PREENCHER:`.
- **HU-CONTEUDO-03:** `prompts/caption_guidelines.md` e `prompts/hashtag_strategy.md` trazem voz e estratégia de hashtag reais; sem `> PREENCHER:`.
- `PromptsLoaderService.load()` loga "todas as seções preenchidas" (nenhum arquivo incompleto).
- `data/templates/` contém os 5 novos templates ativos e nenhum dos 2 genéricos antigos.
- Cada template novo tem `prompt`, `caption_template`, `hashtag_pool` (15-20), `image_count` e `active`.
