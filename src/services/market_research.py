from ..domain.models.content import ContentRequest, MarketResearch
from ..domain.ports import BrainClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SOURCE = "brain-knowledge"
_SYSTEM = (
    "Você é um pesquisador de marketing. A partir de um assunto, produza um "
    "briefing curto e estruturado em português do Brasil que sirva de base "
    "para criar um post de Instagram. Seja objetivo e factual."
)


class MarketResearchError(RuntimeError):
    pass


class MarketResearchService:
    def __init__(self, brain: BrainClient):
        self._brain = brain

    async def run(self, request: ContentRequest) -> MarketResearch:
        if not request.subject.strip():
            raise MarketResearchError("Assunto vazio — não há o que pesquisar.")

        if not self._brain.available:
            logger.warning("Pesquisa de mercado em modo placeholder (cérebro sem credencial).")
            return MarketResearch(
                subject=request.subject,
                summary=f"[PLACEHOLDER] Pesquisa de mercado não configurada. Assunto: {request.subject}.",
                source="placeholder:none",
            )

        logger.info("Pesquisando assunto '%s' (fonte: %s)", request.subject, _SOURCE)
        context = f"Contexto adicional: {request.notes}\n" if request.notes else ""
        prompt = (
            f"Assunto do post: {request.subject}\n{context}\n"
            "Responda em texto corrido com:\n"
            "1) um resumo de 2-3 frases sobre o assunto;\n"
            "2) uma lista de 3-5 pontos-chave (cada um em uma linha começando com '- ');\n"
            "3) uma lista de 2-3 ângulos de abordagem (cada um em uma linha começando com '* ')."
        )
        try:
            raw = await self._brain.complete(_SYSTEM, prompt, max_tokens=700)
        except Exception as exc:
            logger.error("Cérebro falhou na pesquisa [%s: %s]", type(exc).__name__, exc)
            raise MarketResearchError(f"Cérebro falhou na pesquisa: {exc}") from exc

        research = self._parse(request.subject, raw)
        logger.info(
            "Pesquisa concluída para '%s' — %d ponto(s)-chave, %d ângulo(s).",
            request.subject, len(research.key_points), len(research.angles),
        )
        return research

    @staticmethod
    def _parse(subject: str, raw: str) -> MarketResearch:
        summary: list[str] = []
        key_points: list[str] = []
        angles: list[str] = []
        for line in (line.strip() for line in raw.splitlines()):
            if line.startswith("- "):
                key_points.append(line[2:].strip())
            elif line.startswith("* "):
                angles.append(line[2:].strip())
            elif line:
                summary.append(line)
        if not summary and not key_points:
            raise MarketResearchError("Pesquisa retornou conteúdo vazio.")
        return MarketResearch(
            subject=subject, summary=" ".join(summary), key_points=key_points, angles=angles, source=_SOURCE
        )
