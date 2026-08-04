# Diretrizes de criação de imagem

> Regras que valem para TODA imagem. Combinado com `identity.md` e o prompt do template,
> forma o prompt final. Escrever com vocabulário visual e conciso.

## Estética da marca
- **Estilo:** fotográfico realista, editorial de engenharia, studio limpo ("industrial product photography", "editorial"). Nunca render CGI ou plástico de brinquedo.
- **Sensação:** precisão, qualidade, confiabilidade, premium técnico.

## Materiais e realismo físico (CRÍTICO)
- A impressam faz **impressão 3D FDM (filamento termoplástico)** — as peças são de **plástico técnico**, NUNCA metal.
- Materiais reais usados: **PLA, ABS, ASA, PETG, NYLON, TPU, TRITAN, WOOD (compósito com madeira)**.
- A peça impressa deve parecer **termoplástico**: acabamento fosco a semi-brilho, **linhas de camada sutis do FDM** visíveis de perto, superfície de plástico técnico. Cores típicas de filamento: preto, cinza, branco, natural, ou a cor do material.
- ❌ **NUNCA** representar a peça impressa como **metal, aço, cromado, alumínio, ferro fundido ou usinada em metal.** (Ex.: uma engrenagem impressa é de nylon/PETG preto ou cinza fosco — não de aço escovado.)
- Metal/aço pode aparecer só como **contexto de fundo** (bancada, máquina, ferramenta), nunca como a peça-herói impressa.

## Paleta
- Neutros (branco, cinza concreto, grafite, preto técnico) + 1 acento sutil: azul técnico profundo (#1B4D7E).
- Evitar: tons saturados/infantis, neon excessivo, fundos coloridos poluídos.

## Composição e enquadramento
- Formato retrato 4:5 (já em `GEMINI_ASPECT_RATIO`).
- Assunto principal nítido (a peça), profundidade de campo rasa, respiro nas bordas, sem poluição.
- Macro/close para peças; plano médio para a impressora em operação; flat lay para conjunto de peças.

## Iluminação
- Luz de estúdio suave e direcional (realista). Em chão de fábrica, luz mais natural/dura, ainda realista.

## Texto na imagem
- **Padrão: NENHUM texto na imagem.** Toda geração sai como foto limpa, sem título, sem legenda, sem rótulo.
- Texto SÓ é permitido quando **explicitamente pedido** — formato "banner" ou pedido do operador dizendo o texto. Nesse caso: curto (máx. 1 frase + 1 dado), em **português do Brasil, CAIXA ALTA, sem acento**, fonte legível e alto contraste.
- ❌ Nunca inventar texto por conta própria. ❌ Parágrafos ou blocos longos (o modelo erra letras).

## Logo / marca
- **NÃO desenhar logo, marca d'água, símbolo ou assinatura na imagem.** O modelo de imagem inventa logos falsos e deforma letras.
- O logo real da impressam é aplicado **depois**, por sobreposição (Pillow) — ver `assets/brand/README.md`. A geração deve sair **sem nenhum logo**.

## Proibições (hard "never")
- ❌ **Peça impressa com aparência de metal/aço/cromado** (a impressam imprime termoplástico, não metal).
- ❌ Texto na imagem sem pedido explícito.   ❌ Logo/marca d'água desenhado pela IA.
- ❌ Logos/marcas de terceiros.
- ❌ Peça com cara de brinquedo / plástico barato.
- ❌ Anatomia humana estranha (mãos, dedos, rostos distorcidos).
- ❌ Aparência de render CGI fake — buscar sempre realismo fotográfico.
- ❌ Conteúdo sensível, violento ou contra as regras do Instagram.

## Padrão técnico
- Alta resolução, nitidez, qualidade profissional ("industrial product photography", "editorial", "high detail", "sharp focus", "professional lighting").
- Aspect ratio 4:5.

## Montagem do prompt final
[diretrizes de marca] + [tema do template] + [padrão técnico]
Ex.: "Macro product shot of a precision FDM 3D-printed gear in matte black nylon, subtle visible layer lines, resting on a concrete workbench, soft directional studio light, shallow depth of field, neutral palette with subtle blue accent — industrial editorial photography, high detail, no text, 4:5."
