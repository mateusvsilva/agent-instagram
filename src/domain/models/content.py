"""Entidades do novo fluxo "assunto → pesquisa → conteúdo" (HU-BACKEND-01/02/06).

`ContentRequest`  — o assunto que dispara a geração e de onde ele veio.
`MarketResearch`  — contrato de saída da etapa de pesquisa (HU-BACKEND-02).
`WeeklyBriefing`  — direção de conteúdo registrada no Hub (HU-BACKEND-06).

São modelos puros: nenhuma dependência de framework web, banco ou SDK.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SubjectOrigin(str, Enum):
    """De onde veio o assunto do post — usado para log e desempate (DA-03)."""

    TELEGRAM = "telegram"        # pedido pontual "poste sobre X"
    BRIEFING = "briefing"        # briefing semanal do Hub
    TEMPLATE = "template"        # sorteio de template (comportamento legado)


class ContentRequest(BaseModel):
    """O assunto a ser produzido e sua origem."""

    subject: str
    origin: SubjectOrigin
    # Observações livres (ex.: trecho do briefing, instrução do operador no redo).
    notes: str = ""

    @property
    def has_subject(self) -> bool:
        return bool(self.subject and self.subject.strip())


class MarketResearch(BaseModel):
    """Resultado da pesquisa de mercado sobre o assunto.

    Contrato estável que alimenta tanto a geração de imagem quanto a de
    legenda. A FONTE dos dados (web aberta vs. nicho) é decisão pendente do
    usuário (DA-02) e fica isolada atrás do `MarketResearchProvider` — este
    modelo descreve apenas o formato de saída.
    """

    subject: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    angles: list[str] = Field(default_factory=list)
    source: str = "unknown"  # identificador da fonte/provedor usado
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_context(self) -> str:
        """Serializa a pesquisa como contexto textual para os prompts de IA."""
        lines = [f"Assunto: {self.subject}", "", self.summary.strip()]
        if self.key_points:
            lines.append("")
            lines.append("Pontos-chave:")
            lines.extend(f"- {point}" for point in self.key_points)
        if self.angles:
            lines.append("")
            lines.append("Ângulos sugeridos:")
            lines.extend(f"- {angle}" for angle in self.angles)
        return "\n".join(lines).strip()


class WeeklyBriefing(BaseModel):
    """Direção de conteúdo da semana registrada no Hub (HU-BACKEND-06)."""

    agent_id: str = "impressam"
    subject: str
    notes: str = ""
    starts_at: datetime
    ends_at: Optional[datetime] = None

    def is_active(self, at: Optional[datetime] = None) -> bool:
        moment = at or datetime.now(timezone.utc)
        if moment < self.starts_at:
            return False
        if self.ends_at and moment > self.ends_at:
            return False
        return True
