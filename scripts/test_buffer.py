"""Testa a conexão com o Buffer. Sem Telegram, sem OpenAI.

Rode da raiz do projeto (C:\git\impressan):

    # 1) listar canais (descobre o BUFFER_CHANNEL_ID)
    python -m scripts.test_buffer

    # 2) postar uma imagem de teste a partir de uma URL PÚBLICA
    python -m scripts.test_buffer --image-url https://picsum.photos/1080 --caption "Teste Buffer"

Pré-requisito: BUFFER_API_KEY preenchido no .env.
"""
import argparse
import asyncio
import sys

from src.config import get_settings
from src.domain.models.post import ComposedPost
from src.services.buffer_publisher import BufferPublisherService


async def _run(args) -> int:
    settings = get_settings()
    if not settings.buffer_api_key or settings.buffer_api_key in ("", "placeholder"):
        print("ERRO: preencha BUFFER_API_KEY no .env primeiro.")
        return 2

    pub = BufferPublisherService(settings=settings)

    # Sempre lista os canais — é como voce descobre o channelId.
    try:
        channels = await pub.list_channels()
    except Exception as exc:
        print(f"FALHOU ao falar com o Buffer: {type(exc).__name__}: {exc}")
        print("Confira se a BUFFER_API_KEY esta correta.")
        return 1

    if not channels:
        print("Conectado ao Buffer, mas nenhum canal encontrado.")
        print("Conecte sua conta do Instagram no painel do Buffer primeiro.")
        return 1

    print("Canais conectados no Buffer:")
    for ch in channels:
        print(f"  id={ch['id']}  service={ch.get('service')}  nome={ch.get('name')}  org={ch.get('organization')}")
    print("\n>>> Copie o 'id' do canal do Instagram para BUFFER_CHANNEL_ID no .env.")

    if not args.image_url:
        return 0

    # Teste de publicacao real usando uma URL publica.
    if not settings.buffer_channel_id:
        print("\nPara testar a publicacao, preencha BUFFER_CHANNEL_ID no .env e rode de novo com --image-url.")
        return 0

    print(f"\nVou enviar um post de teste no canal {settings.buffer_channel_id}...")
    composed = ComposedPost(
        id="test-buffer",
        template_id="test",
        composed_image_paths=[args.image_url],
        caption=args.caption,
    )
    result = await pub.publish_carousel(composed)
    if result.success:
        print(f"SUCESSO! Post criado no Buffer (id={result.media_id}).")
        print("Veja na fila/Publishing do painel do Buffer.")
        return 0
    print(f"FALHOU: {result.error}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", help="URL publica de imagem para post de teste")
    ap.add_argument("--caption", default="Teste do agente impressam via Buffer", help="legenda")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
