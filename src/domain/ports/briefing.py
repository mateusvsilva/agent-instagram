"""Porta `BriefingRepository` — fonte do briefing semanal (HU-BACKEND-06).

Devolve o briefing ativo do agente, ou `None` se não houver (caso em que o
chamador cai para a lógica padrão de sorteio de template). O formato de
armazenamento é decisão pendente (DA-05 / HU-FRONTEND-01), por isso é plugável.
Implementada hoje por `FileBriefingRepository` (JSON local).
"""
from typing import Optional, Protocol, runtime_checkable

from ..models.content import WeeklyBriefing


@runtime_checkable
class BriefingRepository(Protocol):
    async def get_active(self, agent_id: str) -> Optional[WeeklyBriefing]: ...
