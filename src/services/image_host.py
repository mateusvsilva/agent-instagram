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
        self._api_key = api_key
        self._api_secret = api_secret
        self._url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    def _signature(self, params: dict) -> str:
        to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
        return hashlib.sha1(f"{to_sign}{self._api_secret}".encode()).hexdigest()

    async def upload(self, path: str) -> str:
        timestamp = str(int(time.time()))
        data = {
            "api_key": self._api_key,
            "timestamp": timestamp,
            "signature": self._signature({"timestamp": timestamp}),
        }
        file_path = Path(path)
        async with httpx.AsyncClient(timeout=120.0) as client:
            with file_path.open("rb") as fh:
                resp = await client.post(self._url, data=data, files={"file": (file_path.name, fh, "image/jpeg")})
        if resp.status_code >= 400:
            raise RuntimeError(f"Cloudinary HTTP {resp.status_code}: {resp.text[:300]}")
        secure_url = resp.json().get("secure_url")
        if not secure_url:
            raise RuntimeError(f"Cloudinary não retornou secure_url: {resp.text[:200]}")
        logger.info("Imagem hospedada: %s → %s", file_path.name, secure_url)
        return secure_url


def build_image_uploader(settings: Settings) -> Optional[ImageUploader]:
    if settings.image_host_backend != "cloudinary":
        logger.info("Sem image host configurado (IMAGE_HOST_BACKEND=%s)", settings.image_host_backend)
        return None
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
        logger.warning("IMAGE_HOST_BACKEND=cloudinary mas credenciais ausentes — publicação vai falhar até configurar.")
        return None
    return CloudinaryUploader(settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)
