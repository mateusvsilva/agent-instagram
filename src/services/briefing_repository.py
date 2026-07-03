"""Fonte do briefing semanal consumido pelo agente (HU-BACKEND-06).

O formato de armazenamento do "guia" (arquivo, banco do Hub, ou outro) é
decisão de produto pendente (DA-05) e depende da interface do Hub (HU-FRONTEND-01),
que ainda não existe. Por isso a fonte é uma porta plugável (`BriefingRepository`)
e a implementação entregue é um STUB baseado em arquivo JSON local, claramente
marcado — suficiente para o backend consumir um briefing sem travar o fluxo.

Regra de negócio (HU-BACKEND-06): na AUSÊNCIA de briefing ativo, o repositório
devolve `None` e o chamador cai para a lógica existente (sorteio de template).
"""
import json
from pathlib import Path
from typing import Optional

from ..config import Settings
from ..domain.ports import BriefingRepository
from ..domain.models.content import WeeklyBriefing
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FileBriefingRepository:
    """STUB / PLACEHOLDER — lê o briefing de um JSON local.

    TODO(DA-05 / HU-FRONTEND-01): quando o formato de armazenamento for definido
    e o Hub passar a registrar briefings, trocar esta implementação pela fonte
    real (ex.: tabela no banco compartilhado com o Hub). O contrato
    `BriefingRepository` permanece o mesmo.

    Formato esperado do arquivo (lista de briefings):
        [
          {
            "agent_id": "impressam",
            "subject": "lançamento da coleção de inverno",
            "notes": "foco em conforto",
            "starts_at": "2026-06-16T00:00:00+00:00",
            "ends_at": "2026-06-23T00:00:00+00:00"
          }
        ]
    """

    def __init__(self, path: Path):
        self._path = path

    async def get_active(self, agent_id: str) -> Optional[WeeklyBriefing]:
        briefings = self._load_all()
        active = [b for b in briefings if b.agent_id == agent_id and b.is_active()]
        if not active:
            return None
        # Mais recente (maior starts_at) vence se houver mais de um ativo.
        chosen = max(active, key=lambda b: b.starts_at)
        logger.info("Briefing ativo para agente '%s': %s", agent_id, chosen.subject)
        return chosen

    def _load_all(self) -> list[WeeklyBriefing]:
        if not self._path.exists():
            logger.debug("Sem arquivo de briefing em %s — agente usará o fluxo padrão.", self._path)
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Falha ao ler briefings de %s: %s", self._path, exc)
            return []
        items = data if isinstance(data, list) else [data]
        briefings: list[WeeklyBriefing] = []
        for item in items:
            try:
                briefings.append(WeeklyBriefing.model_validate(item))
            except Exception as exc:  # noqa: BLE001 - ignora entradas malformadas
                logger.warning("Briefing inválido ignorado: %s", exc)
        return briefings


def build_briefing_repository(settings: Settings) -> BriefingRepository:
    """Fábrica do repositório de briefing.

    TODO(DA-05): apontar para a fonte real quando o Hub gravar os briefings.
    """
    path = settings.briefing_file
    return FileBriefingRepository(path)
