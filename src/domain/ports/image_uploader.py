"""Porta `ImageUploader` — hospedagem de imagens para gerar URL pública.

O Buffer não hospeda imagens: exige uma URL pública. Esta porta recebe um
caminho local e devolve a URL pública. Implementada hoje por
`CloudinaryUploader`. Espelha o `Protocol` já usado por `BufferPublisherService`.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageUploader(Protocol):
    async def upload(self, path: str) -> str:
        """Recebe um caminho local e devolve uma URL pública da imagem."""
        ...
