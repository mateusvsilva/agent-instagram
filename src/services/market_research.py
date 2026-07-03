"""Etapa de pesquisa de mercado do pipeline (HU-BACKEND-02).

A pesquisa roda ANTES da imagem e da legenda e alimenta as duas. O CONTRATO
(`ContentRequest` → `MarketResearch`) está fechado; a FONTE dos dados é uma
decisão de produto pendente do usuário (DA-02: web aberta vs. fontes do nicho).
Por isso a fonte é uma porta plugável (`MarketResearchProvider`) e a única
implementação entregue aqui é um STUB explícito.

Regra de negócio (HU-BACKEND-02): se a pesquisa falhar ou vier vazia, o erro é
registrado e o pipeline NÃO segue como se tivesse pesquisado. Esse contrato de
falha é responsabilidade de quem chama (orquestrador): este serviço levanta
`MarketResearchError` em vez de devolver resultado silencioso.
"""
from typing import Optional

from ..domain.ports import BrainClient, MarketResearchProvider
from ..domain.models.content import ContentRequest, MarketResearch
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MarketResearchError(RuntimeError):
    """Pesquisa falhou ou não retornou conteúdo utilizável."""


class StubMarketResearchProvider:
    """STUB / PLACEHOLDER — NÃO é uma fonte de pesquisa real.

    TODO(DA-02): substituir por uma fonte real (busca na web aberta ou fontes
    específicas do nicho) quando o usuário decidir a origem dos dados. Enquanto
    isso, usamos o "cérebro" (Claude) para produzir um briefing estruturado a
    partir do conhecimento do próprio modelo — útil para validar o pipeline
    ponta a ponta, mas SEM garantia de dados atualizados de mercado.

    Se o cérebro não estiver disponível, devolve um esqueleto mínimo apenas
    para o pipeline não quebrar em ambiente sem credencial — claramente marcado
    como placeholder.
    """

    _SYSTEM = (
        "Você é um pesquisador de marketing. A partir de um assunto, produza um "
        "briefing curto e estruturado em português do Brasil que sirva de base "
        "para criar um post de Instagram. Seja objetivo e factual."
    )

    def __init__(self, brain: BrainClient):
        self._brain = brain

    @property
    def source_name(self) -> str:
        return "stub:brain-knowledge"

    async def research(self, request: ContentRequest) -> MarketResearch:
        if not self._brain.available:
            logger.warning(
                "Pesquisa de mercado em modo placeholder sem cérebro — DA-02 ainda pendente."
            )
            return self._placeholder(request)

        prompt = (
            f"Assunto do post: {request.subject}\n"
            f"{('Contexto adicional: ' + request.notes) if request.notes else ''}\n\n"
            "Responda em texto corrido com:\n"
            "1) um resumo de 2-3 frases sobre o assunto;\n"
            "2) uma lista de 3-5 pontos-chave (cada um em uma linha começando com '- ');\n"
            "3) uma lista de 2-3 ângulos de abordagem (cada um em uma linha começando com '* ')."
        )
        try:
            raw = await self._brain.complete(self._SYSTEM, prompt, max_tokens=700)
        except Exception as exc:  # noqa: BLE001 - convertido em erro de domínio
            # Logamos a causa REAL (tipo + mensagem) para distinguir "modelo
            # inválido / erro 4xx da Anthropic" de outras falhas antes de
            # converter no erro de domínio.
            logger.error(
                "Cérebro falhou na pesquisa [%s: %s]", type(exc).__name__, exc
            )
            raise MarketResearchError(f"Cérebro falhou na pesquisa: {exc}") from exc

        return self._parse(request.subject, raw)

    def _parse(self, subject: str, raw: str) -> MarketResearch:
        summary_lines: list[str] = []
        key_points: list[str] = []
        angles: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                key_points.append(stripped[2:].strip())
            elif stripped.startswith("* "):
                angles.append(stripped[2:].strip())
            elif stripped:
                summary_lines.append(stripped)

        summary = " ".join(summary_lines).strip()
        if not summary and not key_points:
            raise MarketResearchError("Pesquisa retornou conteúdo vazio.")

        return MarketResearch(
            subject=subject,
            summary=summary,
            key_points=key_points,
            angles=angles,
            source=self.source_name,
        )

    def _placeholder(self, request: ContentRequest) -> MarketResearch:
        return MarketResearch(
            subject=request.subject,
            summary=(
                f"[PLACEHOLDER] Pesquisa de mercado real ainda não configurada (DA-02). "
                f"Assunto solicitado: {request.subject}."
            ),
            key_points=[],
            angles=[],
            source="placeholder:none",
        )


class MarketResearchService:
    """Orquestra a etapa de pesquisa usando o provedor configurado."""

    def __init__(self, provider: MarketResearchProvider):
        self._provider = provider

    async def run(self, request: ContentRequest) -> MarketResearch:
        if not request.has_subject:
            raise MarketResearchError("Assunto vazio — não há o que pesquisar.")

        logger.info("Pesquisando assunto '%s' (fonte: %s)", request.subject, self._provider.source_name)
        research = await self._provider.research(request)

        if not research.summary and not research.key_points:
            raise MarketResearchError("Pesquisa retornou sem resumo nem pontos-chave.")

        logger.info(
            "Pesquisa concluída para '%s' — %d ponto(s)-chave, %d ângulo(s).",
            request.subject, len(research.key_points), len(research.angles),
        )
        return research


def build_market_research_service(brain: BrainClient, provider: Optional[MarketResearchProvider] = None) -> MarketResearchService:
    """Fábrica da etapa de pesquisa.

    TODO(DA-02): quando a fonte de pesquisa for decidida, injetar aqui o
    provedor real em vez do `StubMarketResearchProvider`.
    """
    return MarketResearchService(provider or StubMarketResearchProvider(brain))
