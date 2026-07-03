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

## Repertório de assuntos (o que mostrar)
- **Mecânica:** engrenagens, guias lineares, pistões, buchas, protótipos de moldes de injeção plástica, dispositivos e berços de fixação para automação, pinças/garras para robôs ("fixture", "jig", "robot gripper").
- **Civil:** maquetes arquitetônicas, moldes para modelagem de gesso.
- **Serviços gerais:** logos para fachadas, objetos personalizados, utensílios.
- **Textura honesta do material:** linhas de camada FDM sutis ou superfície levemente granular de SLS (nylon), acabamento técnico — não esconder que é peça impressa, nem exagerar defeito.
- ⚠️ **Impressoras (FDM/SLS) em operação:** SOMENTE quando o pedido citar a impressora explicitamente — nunca por escolha própria do agente.

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
