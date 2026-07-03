from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from .enums import ApprovalStatus, PostStatus


class GeneratedImage(BaseModel):
    id: str
    post_id: str
    file_path: str
    prompt_used: str
    cost_usd: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dalle_params: dict = Field(default_factory=dict)


class ComposedPost(BaseModel):
    id: str
    template_id: str
    schedule_id: Optional[str] = None
    images: list[GeneratedImage] = Field(default_factory=list)
    composed_image_paths: list[str] = Field(default_factory=list)
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    status: PostStatus = PostStatus.GENERATING
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    attempt: int = 1
    max_attempts: int = 3
    total_cost_usd: float = 0.0
    telegram_message_id: Optional[str] = None
    instagram_media_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    error: Optional[str] = None


class Post(ComposedPost):
    pass


class Metrics(BaseModel):
    total_posts: int
    published: int
    rejected: int
    approval_rate: float
    total_cost_usd: float
    avg_cost_per_post: float
    period: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PublishResult(BaseModel):
    success: bool
    media_id: Optional[str] = None
    error: Optional[str] = None


class SessionStatus(BaseModel):
    logged_in: bool
    username: Optional[str] = None
    last_login: Optional[datetime] = None
    session_file_exists: bool = False


class RateLimitInfo(BaseModel):
    can_post: bool
    last_post_at: Optional[datetime] = None
    cooldown_minutes: int = 30
    minutes_remaining: float = 0.0
