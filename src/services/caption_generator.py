from typing import Optional

from ..domain.models.brand import BrandIdentity
from ..domain.models.content import MarketResearch
from ..domain.models.template import PromptTemplate
from ..domain.ports import BrainClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "Você é o redator social media da marca. Escreva legendas de Instagram em "
    "português do Brasil, únicas, no tom da marca, seguindo as diretrizes "
    "fornecidas. Devolva apenas a legenda final (com hashtags ao fim), sem "
    "comentários, sem aspas e sem cabeçalhos."
)


class CaptionGeneratorService:
    def __init__(self, brain: BrainClient, max_tokens: int = 600):
        self._brain = brain
        self._max_tokens = max_tokens

    async def generate(
        self,
        *,
        subject: str,
        brand: BrandIdentity,
        research: Optional[MarketResearch] = None,
        template: Optional[PromptTemplate] = None,
        instruction: str = "",
        fallback_caption: str = "",
    ) -> str:
        if not self._brain.available:
            logger.info("Cérebro indisponível — usando legenda de fallback do template.")
            return fallback_caption.strip()

        prompt = self._build_prompt(subject, brand, research, template, instruction)
        try:
            caption = await self._brain.complete(_SYSTEM, prompt, max_tokens=self._max_tokens)
        except Exception as exc:
            logger.error(
                "Falha ao gerar legenda por IA [%s: %s] — usando fallback do template.",
                type(exc).__name__, exc,
            )
            return fallback_caption.strip()
        return caption.strip()

    @staticmethod
    def _build_prompt(
        subject: str,
        brand: BrandIdentity,
        research: Optional[MarketResearch],
        template: Optional[PromptTemplate],
        instruction: str,
    ) -> str:
        sections: list[str] = []
        if brand_brief := brand.caption_brief():
            sections.append("=== DIRETRIZES DE MARCA ===\n" + brand_brief)
        if research is not None:
            sections.append("=== PESQUISA DE MERCADO ===\n" + research.as_context())
        if template and template.hashtag_pool:
            sections.append(
                "=== HASHTAGS DISPONÍVEIS (escolha as mais relevantes) ===\n" + " ".join(template.hashtag_pool)
            )
        if instruction.strip():
            sections.append("=== AJUSTE PEDIDO PELO OPERADOR ===\n" + instruction.strip())
        sections.append(f"=== TAREFA ===\nEscreva a legenda do post sobre: {subject}")
        return "\n\n".join(sections)
