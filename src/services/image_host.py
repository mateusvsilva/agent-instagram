"""Hospedagem de imagens para gerar URLs públicas exigidas pelo Buffer.

O Buffer não hospeda imagens: ele baixa a imagem de uma URL pública na hora de
criar o post. Como o agente gera arquivos locais, subimos cada imagem para um
host e devolvemos a URL.

Backend padrão: Cloudinary (tier grátis, sem SDK — usamos a REST API assinada
via httpx). Se nada estiver configurado, retorna None e o publisher avisa.
"""
import hashlib
import time
from pathlib import Path
from typing import Optional

import httpx

from ..config import Settings
from ..domain.ports import ImageUploader
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CloudinaryUploader:
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        self._cloud_name = cloud_name
        self._api_key = api_key
        self._api_secret = api_secret
        self._url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    def _signature(self, params: dict) -> str:
        # Cloudinary: ordena os params alfabeticamente, junta como query string,
        # concatena o api_secret e tira o SHA-1.
        to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
        return hashlib.sha1(f"{to_sign}{self._api_secret}".encode()).hexdigest()

    async def upload(self, path: str) -> str:
        timestamp = int(time.time())
        sign_params = {"timestamp": timestamp}
        signature = self._signature(sign_params)
        data = {
            "api_key": self._api_key,
            "timestamp": str(timestamp),
            "signature": signature,
        }
        file_path = Path(path)
        async with httpx.AsyncClient(timeout=120.0) as client:
            with file_path.open("rb") as fh:
                resp = await client.post(
                    self._url,
                    data=data,
                    files={"file": (file_path.name, fh, "image/jpeg")},
                )
        if resp.status_code >= 400:
            raise RuntimeError(f"Cloudinary HTTP {resp.status_code}: {resp.text[:300]}")
        secure_url = resp.json().get("secure_url")
        if not secure_url:
            raise RuntimeError(f"Cloudinary não retornou secure_url: {resp.text[:200]}")
        logger.info("Imagem hospedada: %s → %s", file_path.name, secure_url)
        return secure_url


def build_image_uploader(settings: Settings) -> Optional[ImageUploader]:
    backend = (settings.image_host_backend or "none").lower()
    if backend == "cloudinary":
        if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
            logger.warning(
                "IMAGE_HOST_BACKEND=cloudinary mas credenciais ausentes — "
                "publicação de imagens locais vai falhar até configurar."
            )
            return None
        return CloudinaryUploader(
            settings.cloudinary_cloud_name,
            settings.cloudinary_api_key,
            settings.cloudinary_api_secret,
        )
    logger.info("Sem image host configurado (IMAGE_HOST_BACKEND=%s)", backend)
    return None
