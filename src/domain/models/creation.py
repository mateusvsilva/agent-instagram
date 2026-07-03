from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .post import ComposedPost


class CreationState(str, Enum):
    AWAITING_BRIEF = "awaiting_brief"
    AWAITING_FOLLOWUP = "awaiting_followup"
    ITERATING = "iterating"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPOSING = "composing"
    AWAITING_PUBLISH = "awaiting_publish"
    AWAITING_CAPTION_FEEDBACK = "awaiting_caption_feedback"
    DONE = "done"
    CANCELLED = "cancelled"


class CreationMode(str, Enum):
    CLEAN = "clean"
    BANNER = "banner"
    AUTO = "auto"


class CreationSession(BaseModel):
    chat_id: int
    post_id: str
    state: CreationState = CreationState.AWAITING_BRIEF
    brief: str = ""
    mode: CreationMode = CreationMode.AUTO
    current_prompt: str = ""
    current_image_path: Optional[str] = None
    rounds: int = 0
    total_cost_usd: float = 0.0
    composed: Optional[ComposedPost] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
