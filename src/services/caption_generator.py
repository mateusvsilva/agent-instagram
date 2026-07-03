"""Geração de legenda por IA, única por post (HU-BACKEND-03).

Substitui o uso literal de `caption_template`: a legenda passa a ser escrita
pelo "cérebro" seguindo as diretrizes de marca (`caption_guidelines.md` +
`hashtag_strategy.md`, via `BrandIdentity`) e o contexto da pesquisa de mercado
(`MarketResearch`).

Fallback: se o cérebro não estiver disponível (sem `ANTHROPIC_API_KEY`) ou
falhar, cai para a legenda do template — assim o pipeline nunca trava por falta
da capacidade de IA, mantendo retrocompatibilidade.
"""
from typing import Optional

from ..domain.ports import BrainClient
from ..domain.models.brand import BrandIdentity
from ..domain.models.content import MarketResearch
from ..domain.models.template import PromptTemplate
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "Você é o redator social media da marca. Escreva legendas de Instagram em "
    "português do Brasil, únicas, no tom da marca, seguindo as diretrizes "
    "fornecidas. Devolva apenas a legenda final (com hashtags ao fim), sem "
    "comentários, sem aspas e sem cabeçalhos."
)

# Origem da legenda — exposta ao operador no preview (PEND-04): degradar para o
# template não pode ser silencioso, senão a revisão aprova texto genérico
# achando que foi redigido pela IA no tom da marca.
CAPTION_SOURCE_AI = "ia"
CAPTION_SOURCE_FALLBACK = "fallback"


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
    ) -> tuple[str, str]:
        """Gera a legenda. `instruction` carrega pedidos de ajuste do redo.

        Retorna `(legenda, origem)`, onde origem é `CAPTION_SOURCE_AI` ou
        `CAPTION_SOURCE_FALLBACK`.
        """
        if not self._brain.available:
            logger.info("Cérebro indisponível — usando legenda de fallback do template.")
            return fallback_caption.strip(), CAPTION_SOURCE_FALLBACK

        prompt = self._build_prompt(
            subject=subject,
            brand=brand,
            research=research,
            template=template,
            instruction=instruction,
        )
        try:
            caption = await self._brain.complete(_SYSTEM, prompt, max_tokens=self._max_tokens)
        except Exception as exc:  # noqa: BLE001 - degrada para fallback, não derruba o post
            # Logamos a causa REAL (tipo + mensagem) para distinguir "modelo
            # inválido / erro 4xx da Anthropic" de outras falhas — sem isso o
            # fallback é silencioso e parece "sem API key".
            logger.error(
                "Falha ao gerar legenda por IA [%s: %s] — usando fallback do template.",
                type(exc).__name__, exc,
            )
            return fallback_caption.strip(), CAPTION_SOURCE_FALLBACK

        return caption.strip(), CAPTION_SOURCE_AI

    def _build_prompt(
        self,
        *,
        subject: str,
        brand: BrandIdentity,
        research: Optional[MarketResearch],
        template: Optional[PromptTemplate],
        instruction: str,
    ) -> str:
        sections: list[str] = []

        brand_brief = brand.caption_brief()
        if brand_brief:
            sections.append("=== DIRETRIZES DE MARCA ===\n" + brand_brief)

        if research is not None:
            sections.append("=== PESQUISA DE MERCADO ===\n" + research.as_context())

        if template and template.hashtag_pool:
            sections.append("=== HASHTAGS DISPONÍVEIS (escolha as mais relevantes) ===\n" + " ".join(template.hashtag_pool))

        if instruction.strip():
            sections.append("=== AJUSTE PEDIDO PELO OPERADOR ===\n" + instruction.strip())

        sections.append(f"=== TAREFA ===\nEscreva a legenda do post sobre: {subject}")
        return "\n\n".join(sections)
