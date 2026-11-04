from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_GRAPHQL_ENUM = r"^[A-Za-z_][A-Za-z0-9_]*$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    image_provider: Literal["gemini", "openai"] = Field("gemini", alias="IMAGE_PROVIDER")

    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash-image", alias="GEMINI_MODEL")
    gemini_aspect_ratio: str = Field("4:5", alias="GEMINI_ASPECT_RATIO")
    gemini_cost_per_image: float = Field(0.039, alias="GEMINI_COST_PER_IMAGE")

    brain_provider: Literal["openai", "anthropic"] = Field("openai", alias="BRAIN_PROVIDER")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    brain_model: str = Field("claude-opus-4-8", alias="BRAIN_MODEL")
    openai_brain_model: str = Field("gpt-4o-mini", alias="OPENAI_BRAIN_MODEL")
    prompts_dir: Path = Field(Path("./prompts"), alias="PROMPTS_DIR")

    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    dalle_model: str = Field("dall-e-3", alias="DALLE_MODEL")
    dalle_default_size: str = Field("1024x1792", alias="DALLE_DEFAULT_SIZE")
    dalle_default_quality: str = Field("hd", alias="DALLE_DEFAULT_QUALITY")

    daily_budget_usd: float = Field(2.00, alias="DAILY_BUDGET_USD")
    monthly_budget_usd: float = Field(50.00, alias="MONTHLY_BUDGET_USD")
    budget_alert_threshold: float = Field(0.8, alias="BUDGET_ALERT_THRESHOLD")

    buffer_api_key: str = Field("", alias="BUFFER_API_KEY")
    buffer_channel_id: str = Field("", alias="BUFFER_CHANNEL_ID")
    buffer_api_url: str = Field("https://api.buffer.com", alias="BUFFER_API_URL")
    buffer_scheduling_mode: str = Field(
        "addToQueue", alias="BUFFER_SCHEDULING_MODE", pattern=_GRAPHQL_ENUM
    )
    buffer_instagram_post_type: str = Field(
        "post", alias="BUFFER_INSTAGRAM_POST_TYPE", pattern=_GRAPHQL_ENUM
    )

    image_host_backend: Literal["cloudinary", "none"] = Field("cloudinary", alias="IMAGE_HOST_BACKEND")
    cloudinary_cloud_name: str = Field("", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field("", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field("", alias="CLOUDINARY_API_SECRET")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: int = Field(..., alias="TELEGRAM_CHAT_ID")
    telegram_approval_timeout: int = Field(7200, alias="TELEGRAM_APPROVAL_TIMEOUT")
    telegram_allowed_user_ids: str = Field("", alias="TELEGRAM_ALLOWED_USER_IDS", pattern=r"^[\d\s,]*$")

    scheduler_timezone: str = Field("America/Sao_Paulo", alias="SCHEDULER_TIMEZONE")
    scheduler_enabled: bool = Field(True, alias="SCHEDULER_ENABLED")
    scheduler_retry_delay_seconds: int = Field(300, alias="SCHEDULER_RETRY_DELAY_SECONDS")

    db_path: Path = Field(Path("./data/db/agent.db"), alias="DB_PATH")
    briefing_file: Path = Field(Path("./data/briefing.json"), alias="BRIEFING_FILE")
    schedules_file: Path = Field(Path("./data/schedules.json"), alias="SCHEDULES_FILE")
    log_file: Path = Field(Path("./data/agent.log"), alias="LOG_FILE")
    agent_id: str = Field("impressam", alias="AGENT_ID")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    post_cooldown_minutes: int = Field(30, alias="POST_COOLDOWN_MINUTES")
    max_redo_attempts: int = Field(3, alias="MAX_REDO_ATTEMPTS")
    templates_dir: Path = Field(Path("./data/templates"), alias="TEMPLATES_DIR")
    images_dir: Path = Field(Path("./data/images"), alias="IMAGES_DIR")

    creation_session_timeout: int = Field(1800, alias="CREATION_SESSION_TIMEOUT")
    creation_max_rounds: int = Field(12, alias="CREATION_MAX_ROUNDS")

    @property
    def allowed_user_ids(self) -> list[int]:
        ids = [int(part) for part in self.telegram_allowed_user_ids.split(",") if part.strip()]
        return ids or [self.telegram_chat_id]


@lru_cache
def get_settings() -> Settings:
    return Settings()
