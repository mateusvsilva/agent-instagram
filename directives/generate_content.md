# Directive: Generate Content (Caption + Hashtags)

## Goal
Given a user message describing the intent of a post, generate a compelling Instagram caption with relevant hashtags using an AI model.

## Inputs
- `message` (str): The user's raw message or content brief (e.g., "Post sobre lançamento do nosso novo produto de skincare")
- `tone` (str, optional): Desired tone — default from `.env` (`POST_TONE`). Options: `engaging`, `professional`, `casual`, `inspirational`
- `language` (str, optional): Target language — default from `.env` (`POST_LANGUAGE`). Example: `pt-BR`, `en-US`

## Tool to Use
- **Script**: `execution/generate_caption.py`
- **AI Provider**: Gemini API (primary) or OpenAI (fallback)

## Output
- File: `.tmp/caption.json`
```json
{
  "caption": "Texto da legenda aqui, formatado para Instagram...",
  "hashtags": "#skincare #beleza #lancamento #novidade #produtonatural",
  "full_post": "Texto da legenda aqui...\n\n#skincare #beleza #lancamento"
}
```

## Instructions
1. Load the user's message and optional parameters.
2. Call `execution/generate_caption.py` with the message, tone, and language.
3. Review the generated caption for:
   - Clarity and alignment with the user's intent
   - Hashtag relevance (max 30 hashtags for Instagram)
   - Appropriate length (Instagram: up to 2,200 characters, ideal: 125–150)
4. If the caption is not satisfactory, re-run the script with additional context or adjusted tone.
5. Save the final caption to `.tmp/caption.json`.

## Edge Cases
- If the message is too vague, ask the user for more detail before generating.
- If the AI returns more than 30 hashtags, truncate to the 30 most relevant.
- Instagram penalizes repetitive/banned hashtags — avoid generic spam tags.

## Example
**Input**: "Nosso café acabou de ganhar um prêmio regional de barista"
**Output caption**: "☕ Orgulho é pouco! Nosso café acabou de ser premiado como melhor da região no campeonato de barismo. Cada xícara tem uma história — e essa é especialmente especial. Obrigado a todos que fazem parte dessa jornada! 🏆"
**Hashtags**: `#cafe #barismo #premiado #cafeespecial #saborunico #barista`
