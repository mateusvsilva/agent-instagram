"""
generate_image.py
-----------------
Layer 3 — Execution Script

Generates an image for an Instagram post using AI, or copies a user-provided image.

Usage:
    python execution/generate_image.py --prompt "..." [--provider gemini]
    python execution/generate_image.py --user-file "path/to/image.jpg"

Output:
    .tmp/media/image.png
"""

import os
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OUTPUT_PATH = Path(".tmp/media/image.png")


def generate_with_gemini_imagen(prompt: str) -> None:
    """Generate image using Google Gemini Imagen API."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    genai.configure(api_key=api_key)

    # Use Imagen 3 for high quality output
    imagen = genai.ImageGenerationModel("imagen-3.0-generate-001")
    result = imagen.generate_images(
        prompt=prompt,
        number_of_images=1,
        aspect_ratio="1:1",  # Square — best for Instagram feed
        safety_filter_level="block_some",
        person_generation="allow_adult",
    )

    if not result.images:
        raise RuntimeError("Imagen returned no images")

    image = result.images[0]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image._pil_image.save(OUTPUT_PATH, format="PNG")


def generate_with_openai_dalle(prompt: str) -> None:
    """Generate image using OpenAI DALL-E 3 (fallback)."""
    import requests
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(img_response.content)


def copy_user_file(user_file_path: str) -> None:
    """Copy a user-provided image to the output path."""
    from PIL import Image

    source = Path(user_file_path)
    if not source.exists():
        raise FileNotFoundError(f"File not found: {user_file_path}")

    # Validate it's a valid image
    with Image.open(source) as img:
        width, height = img.size
        if width < 320 or height < 320:
            raise ValueError(f"Image too small: {width}x{height}px. Minimum: 320x320px")
        print(f"[generate_image] Image validated: {width}x{height}px, format: {img.format}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, OUTPUT_PATH)


def main():
    parser = argparse.ArgumentParser(description="Generate or prepare image for Instagram")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="Text prompt for AI image generation")
    group.add_argument("--user-file", help="Path to a user-provided image file")
    parser.add_argument(
        "--provider",
        default=os.getenv("MEDIA_PROVIDER", "gemini"),
        choices=["gemini", "openai"],
        help="AI provider for image generation",
    )
    args = parser.parse_args()

    if args.user_file:
        print(f"[generate_image] Copying user-provided file: {args.user_file}")
        copy_user_file(args.user_file)
    else:
        print(f"[generate_image] Generating image via {args.provider}...")
        print(f"[generate_image] Prompt: {args.prompt[:100]}...")

        try:
            if args.provider == "gemini":
                generate_with_gemini_imagen(args.prompt)
            else:
                generate_with_openai_dalle(args.prompt)
        except Exception as e:
            fallback = "openai" if args.provider == "gemini" else "gemini"
            print(f"[generate_image] Primary provider failed: {e}")
            print(f"[generate_image] Trying fallback: {fallback}...")
            if fallback == "openai":
                generate_with_openai_dalle(args.prompt)
            else:
                generate_with_gemini_imagen(args.prompt)

    print(f"[generate_image] ✅ Image saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
