from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SubjectOrigin(str, Enum):
    TELEGRAM = "telegram"
    BRIEFING = "briefing"
    TEMPLATE = "template"


class ContentRequest(BaseModel):
    subject: str
    origin: SubjectOrigin
    notes: str = ""


class MarketResearch(BaseModel):
    subject: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    angles: list[str] = Field(default_factory=list)
    source: str = "unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_context(self) -> str:
        lines = [f"Assunto: {self.subject}", "", self.summary.strip()]
        if self.key_points:
            lines += ["", "Pontos-chave:", *(f"- {point}" for point in self.key_points)]
        if self.angles:
            lines += ["", "Ângulos sugeridos:", *(f"- {angle}" for angle in self.angles)]
        return "\n".join(lines).strip()


class WeeklyBriefing(BaseModel):
    agent_id: str = "impressam"
    subject: str
    notes: str = ""
    starts_at: datetime
    ends_at: Optional[datetime] = None

    def is_active(self, at: Optional[datetime] = None) -> bool:
        moment = at or datetime.now(timezone.utc)
        return self.starts_at <= moment and (self.ends_at is None or moment <= self.ends_at)
