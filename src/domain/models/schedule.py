from typing import Optional
from pydantic import BaseModel
from .enums import TemplateSelection


class Schedule(BaseModel):
    id: str
    cron: str
    timezone: str = "America/Sao_Paulo"
    enabled: bool = True
    template_id: Optional[str] = None
    template_selection: TemplateSelection = TemplateSelection.RANDOM
    max_retries: int = 3
    cooldown_minutes: int = 30
