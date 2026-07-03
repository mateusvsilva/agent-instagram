"""Portas (contratos) do agente, tornadas explícitas via `typing.Protocol`.

Cada porta reflete EXATAMENTE a assinatura pública que o pipeline (`main.py`) e
os colaboradores já usam hoje. São contratos estruturais: um adaptador concreto
satisfaz uma porta apenas por ter os métodos/assinaturas corretos, sem herança.

As portas importam apenas modelos de domínio (`src/domain/models/...`) e a stdlib —
nunca infraestrutura ou SDKs externos.
"""
from .brain import BrainClient
from .briefing import BriefingRepository
from .image_generator import ImageGenerator
from .image_uploader import ImageUploader
from .market_research import MarketResearchProvider
from .publisher import Publisher

__all__ = [
    "BrainClient",
    "BriefingRepository",
    "ImageGenerator",
    "ImageUploader",
    "MarketResearchProvider",
    "Publisher",
]
