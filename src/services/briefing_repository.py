import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from ..domain.models.content import WeeklyBriefing
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FileBriefingRepository:
    def __init__(self, path: Path):
        self._path = path

    async def get_active(self, agent_id: str) -> Optional[WeeklyBriefing]:
        active = [b for b in self._load_all() if b.agent_id == agent_id and b.is_active()]
        if not active:
            return None
        chosen = max(active, key=lambda b: b.starts_at)
        logger.info("Briefing ativo para agente '%s': %s", agent_id, chosen.subject)
        return chosen

    def _load_all(self) -> list[WeeklyBriefing]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Falha ao ler briefings de %s: %s", self._path, exc)
            return []
        briefings: list[WeeklyBriefing] = []
        for item in data if isinstance(data, list) else [data]:
            try:
                briefings.append(WeeklyBriefing.model_validate(item))
            except ValidationError as exc:
                logger.warning("Briefing inválido ignorado: %s", exc)
        return briefings
