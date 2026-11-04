import argparse
import asyncio
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from src.config import get_settings
from src.domain.models.post import ComposedPost
from src.domain.models.template import PromptTemplate
from src.main import build_image_generator
from src.services.buffer_publisher import BufferPublisherService
from src.services.image_host import build_image_uploader
from src.services.post_composer import PostComposerService
from src.utils.cost_tracker import BudgetTracker

_POST_ID = "test-e2e"


def _step(name: str) -> None:
    print(f"\n=== ETAPA: {name} ===")


def _fail(step: str, exc: Exception) -> int:
    print(f"\n❌ FALHOU NA ETAPA [{step}]: {type(exc).__name__}: {exc}")
    return 1


def _load_template(template_id: str, settings) -> PromptTemplate:
    path = Path(settings.templates_dir) / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template não encontrado: {path}")
    return PromptTemplate(**json.loads(path.read_text(encoding="utf-8")))


def _build_template(args) -> PromptTemplate:
    prompt = args.prompt or "A serene minimalist landscape at golden hour, editorial photography, high detail"
    return PromptTemplate(
        id=_POST_ID,
        name="Teste E2E",
        prompt=prompt,
        caption_template="Teste de ponta a ponta do agente impressam.",
        hashtag_pool=["#impressam", "#teste"],
        image_count=args.count,
    )


async def _run(args) -> int:
    settings = get_settings()

    provider = (settings.image_provider or "gemini").lower()
    _step(f"GERAÇÃO DE IMAGEM (provedor: {provider})")
    if provider == "openai":
        if not settings.openai_api_key or settings.openai_api_key in ("", "sk-placeholder"):
            print("ERRO: preencha OPENAI_API_KEY no .env (https://platform.openai.com/api-keys).")
            return 2
    elif not settings.gemini_api_key:
        print("ERRO: preencha GEMINI_API_KEY no .env (https://aistudio.google.com/apikey).")
        return 2
    budget = BudgetTracker(
        daily_limit=settings.daily_budget_usd,
        monthly_limit=settings.monthly_budget_usd,
        alert_threshold=settings.budget_alert_threshold,
    )
    try:
        generator = build_image_generator(settings, budget)
        template = _load_template(args.template, settings) if args.template else _build_template(args)
        images = await generator.generate(template=template, post_id=_POST_ID, count=args.count)
    except Exception as exc:
        return _fail(f"IMAGEM/{provider.upper()}", exc)
    print(f"OK: {len(images)} imagem(ns) gerada(s).")
    for img in images:
        print(f"   {img.file_path}")

    _step("COMPOSE (redimensiona/valida carrossel)")
    try:
        composer = PostComposerService(settings=settings)
        composed = await composer.compose(images=images, template=template, post_id=_POST_ID)
    except Exception as exc:
        return _fail("COMPOSE", exc)
    print(f"OK: {len(composed.composed_image_paths)} imagem(ns) composta(s).")

    _step("CLOUDINARY (hospedagem → URL pública)")
    uploader = build_image_uploader(settings)
    if uploader is None:
        print("ERRO: image host não configurado. Preencha CLOUDINARY_* no .env.")
        return 2
    try:
        urls = [await uploader.upload(path) for path in composed.composed_image_paths]
    except Exception as exc:
        return _fail("CLOUDINARY", exc)
    print(f"OK: {len(urls)} URL(s) pública(s) gerada(s).")
    for url in urls:
        print(f"   {url}")

    _step("BUFFER (publicação)")
    if not settings.buffer_api_key or not settings.buffer_channel_id:
        print("ERRO: preencha BUFFER_API_KEY e BUFFER_CHANNEL_ID no .env.")
        return 2
    publisher = BufferPublisherService(settings=settings, image_uploader=uploader)

    if not args.publish:
        try:
            session = await publisher.check_session()
        except Exception as exc:
            return _fail("BUFFER", exc)
        if not session.logged_in:
            print("❌ FALHOU NA ETAPA [BUFFER]: credencial do Buffer inválida (não autenticou).")
            return 1
        print("OK (DRY-RUN): Buffer autenticado e URLs prontas — publicação NÃO realizada.")
        print("   Para publicar de verdade, rode novamente com --publish.")
        return 0

    post = ComposedPost(
        id=_POST_ID,
        template_id=template.id,
        composed_image_paths=urls,
        caption=composed.caption,
    )
    try:
        result = await publisher.publish_carousel(post)
    except Exception as exc:
        return _fail("BUFFER", exc)
    if not result.success:
        print(f"❌ FALHOU NA ETAPA [BUFFER]: {result.error}")
        return 1
    print(f"OK: post criado no Buffer (id={result.media_id}). Veja na fila/Publishing.")

    print("\n✅ SUCESSO! Pipeline Gemini → Cloudinary → Buffer concluído.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Teste ponta a ponta sem Telegram (HU-BACKEND-07).")
    ap.add_argument("--prompt", help="prompt livre para a imagem")
    ap.add_argument("--template", help="id de um template em data/templates/")
    ap.add_argument("--count", type=int, default=1, help="quantas imagens gerar")
    ap.add_argument(
        "--publish",
        action="store_true",
        help="publica de verdade no Buffer (padrão é dry-run, que NÃO publica)",
    )
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
