"""Testa a geração de imagem com o Gemini. Sem Telegram, sem Buffer.

Rode da raiz do projeto (C:\git\impressan):

    # gera 1 imagem a partir de um prompt livre
    python -m scripts.test_gemini --prompt "Um café aconchegante ao pôr do sol, foto editorial"

    # gera usando um template existente (pega o prompt do template)
    python -m scripts.test_gemini --template sunset_landscape

A imagem é salva em data/images/test-gemini/.
Pré-requisito: GEMINI_API_KEY preenchido no .env.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from src.config import get_settings
from src.domain.models.template import PromptTemplate
from src.services.gemini_image_generator import GeminiImageGeneratorService
from src.utils.cost_tracker import BudgetTracker


def _load_template(template_id: str, settings) -> PromptTemplate:
    path = Path(settings.templates_dir) / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template não encontrado: {path}")
    return PromptTemplate(**json.loads(path.read_text(encoding="utf-8")))


async def _run(args) -> int:
    settings = get_settings()
    if not settings.gemini_api_key:
        print("ERRO: preencha GEMINI_API_KEY no .env primeiro (https://aistudio.google.com/apikey).")
        return 2

    budget = BudgetTracker(
        daily_limit=settings.daily_budget_usd,
        monthly_limit=settings.monthly_budget_usd,
        alert_threshold=settings.budget_alert_threshold,
    )
    try:
        gen = GeminiImageGeneratorService(settings=settings, budget_tracker=budget)
    except Exception as exc:
        print(f"FALHOU ao iniciar o Gemini: {exc}")
        return 1

    if args.template:
        template = _load_template(args.template, settings)
    else:
        prompt = args.prompt or "A serene minimalist landscape at golden hour, editorial photography, high detail"
        template = PromptTemplate(
            id="test-gemini",
            name="Teste",
            prompt=prompt,
            caption_template="{prompt}",
            image_count=args.count,
        )

    print(f"Modelo: {settings.gemini_model} | aspect_ratio: {settings.gemini_aspect_ratio}")
    print(f"Gerando {args.count} imagem(ns)...")
    try:
        images = await gen.generate(template=template, post_id="test-gemini", count=args.count)
    except Exception as exc:
        print(f"FALHOU na geração: {type(exc).__name__}: {exc}")
        return 1

    print(f"\nSUCESSO! {len(images)} imagem(ns) gerada(s):")
    for img in images:
        print(f"  {img.file_path}  (custo estimado ${img.cost_usd:.3f})")
    print(f"\nGasto registrado nesta sessão: ${budget.daily_spent:.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", help="prompt livre para a imagem")
    ap.add_argument("--template", help="id de um template em data/templates/")
    ap.add_argument("--count", type=int, default=1, help="quantas imagens gerar")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
