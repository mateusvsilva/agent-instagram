from typing import Optional, Protocol, runtime_checkable

from ..models.content import WeeklyBriefing


@runtime_checkable
class BriefingRepository(Protocol):
    async def get_active(self, agent_id: str) -> Optional[WeeklyBriefing]: ...
