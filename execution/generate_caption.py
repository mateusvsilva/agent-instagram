"""
generate_caption.py
-------------------
Layer 3 — Execution Script

Generates an Instagram caption and hashtags from a user message using AI.

Usage:
    python execution/generate_caption.py --message "..." [--tone engaging] [--language pt-BR]

Output:
    .tmp/caption.json
"""

import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Output path ───────────────────────────────────────────────────────────────
OUTPUT_PATH = Path(".tmp/caption.json")
DEFAULT_PROMPT_FILE = Path(
    os.getenv("CAPTION_PROMPT_FILE", "directives/caption_additional_prompt.md")
)

# ─── Prompt template ──────────────────────────────────────────────────────────
CAPTION_PROMPT = """You are an expert Instagram content creator.

Given the following brief, write an engaging Instagram caption and a list of relevant hashtags.

Brief: {message}
Tone: {tone}
Language: {language}

Rules:
- Caption should be between 100–200 words
- Use emojis naturally
- Hashtags: 10–20, highly relevant, not banned/spammy
- Format the response as valid JSON only, no extra text

Respond ONLY with this JSON structure:
{{
  "caption": "your caption text here",
  "hashtags": "#tag1 #tag2 #tag3",
  "full_post": "caption text here\\n\\n#tag1 #tag2 #tag3"
}}"""


def load_additional_prompt(prompt_file: str) -> str:
    """Read extra instructions from a markdown file."""
    path = Path(prompt_file)

    if not path.exists():
        print(f"[generate_caption] Prompt file not found, skipping: {path}")
        return ""

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        print(f"[generate_caption] Prompt file is empty, skipping: {path}")
        return ""

    print(f"[generate_caption] Loaded additional prompt from {path}")
    return content


def build_prompt(message: str, tone: str, language: str, additional_prompt: str) -> str:
    """Build final prompt with base template + optional custom instructions."""
    prompt = CAPTION_PROMPT.format(message=message, tone=tone, language=language)
    if additional_prompt:
        prompt += (
            "\n\nAdditional instructions (must be followed):\n"
            f"{additional_prompt}"
        )
    return prompt


def generate_with_gemini(message: str, tone: str, language: str, additional_prompt: str) -> dict:
    """Generate caption using Google Gemini API."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = build_prompt(message, tone, language, additional_prompt)
    response = model.generate_content(prompt)

    # Strip markdown code fences if present
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)


def generate_with_openai(message: str, tone: str, language: str, additional_prompt: str) -> dict:
    """Generate caption using OpenAI API (fallback)."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)
    prompt = build_prompt(message, tone, language, additional_prompt)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def main():
    parser = argparse.ArgumentParser(description="Generate Instagram caption with AI")
    parser.add_argument("--message", required=True, help="Content brief / user message")
    parser.add_argument(
        "--tone",
        default=os.getenv("POST_TONE", "engaging"),
        help="Tone: engaging, professional, casual, inspirational",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("POST_LANGUAGE", "pt-BR"),
        help="Language code, e.g. pt-BR, en-US",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("MEDIA_PROVIDER", "gemini"),
        choices=["gemini", "openai"],
        help="AI provider to use",
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_FILE),
        help="Markdown file with extra prompt instructions",
    )
    args = parser.parse_args()

    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[generate_caption] Generating caption via {args.provider}...")
    print(f"[generate_caption] Message: {args.message[:80]}...")
    additional_prompt = load_additional_prompt(args.prompt_file)

    try:
        if args.provider == "gemini":
            result = generate_with_gemini(args.message, args.tone, args.language, additional_prompt)
        else:
            result = generate_with_openai(args.message, args.tone, args.language, additional_prompt)
    except Exception as e:
        print(f"[generate_caption] Primary provider failed: {e}")
        fallback = "openai" if args.provider == "gemini" else "gemini"
        print(f"[generate_caption] Trying fallback: {fallback}...")
        if fallback == "openai":
            result = generate_with_openai(args.message, args.tone, args.language, additional_prompt)
        else:
            result = generate_with_gemini(args.message, args.tone, args.language, additional_prompt)

    # Validate hashtag count (Instagram max: 30)
    hashtags = result.get("hashtags", "").split()
    if len(hashtags) > 30:
        print(f"[generate_caption] Truncating hashtags from {len(hashtags)} to 30")
        result["hashtags"] = " ".join(hashtags[:30])
        result["full_post"] = result["caption"] + "\n\n" + result["hashtags"]

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[generate_caption] ✅ Caption saved to {OUTPUT_PATH}")
    print(f"[generate_caption] Caption preview: {result['caption'][:100]}...")
    print(f"[generate_caption] Hashtags ({len(hashtags)}): {result['hashtags']}")


if __name__ == "__main__":
    main()
