from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Provedor de imagem: "gemini" (Google) ou "openai" (DALL-E)
    image_provider: str = Field("gemini", alias="IMAGE_PROVIDER")

    # Gemini (Google) — gere a chave em https://aistudio.google.com/apikey
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash-image", alias="GEMINI_MODEL")
    gemini_aspect_ratio: str = Field("4:5", alias="GEMINI_ASPECT_RATIO")
    gemini_cost_per_image: float = Field(0.039, alias="GEMINI_COST_PER_IMAGE")

    # Claude (Anthropic) — o "cérebro": pesquisa de mercado + redação de legenda
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    brain_model: str = Field("claude-opus-4-8", alias="BRAIN_MODEL")
    prompts_dir: Path = Field(Path("./prompts"), alias="PROMPTS_DIR")

    # Cérebro de texto configurável: "openai" ou "anthropic"
    brain_provider: str = Field("openai", alias="BRAIN_PROVIDER")
    openai_brain_model: str = Field("gpt-4o-mini", alias="OPENAI_BRAIN_MODEL")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    dalle_model: str = Field("dall-e-3", alias="DALLE_MODEL")
    dalle_default_size: str = Field("1024x1792", alias="DALLE_DEFAULT_SIZE")
    dalle_default_quality: str = Field("hd", alias="DALLE_DEFAULT_QUALITY")
    dalle_default_style: str = Field("vivid", alias="DALLE_DEFAULT_STYLE")

    # Budget control
    daily_budget_usd: float = Field(2.00, alias="DAILY_BUDGET_USD")
    monthly_budget_usd: float = Field(50.00, alias="MONTHLY_BUDGET_USD")
    budget_alert_threshold: float = Field(0.8, alias="BUDGET_ALERT_THRESHOLD")

    # Buffer (publisher oficial via API GraphQL)
    buffer_api_key: str = Field("", alias="BUFFER_API_KEY")
    buffer_channel_id: str = Field("", alias="BUFFER_CHANNEL_ID")
    buffer_api_url: str = Field("https://api.buffer.com", alias="BUFFER_API_URL")
    # "addToQueue" usa os horários da sua fila no Buffer; "now" tenta publicar imediato.
    buffer_scheduling_mode: str = Field("addToQueue", alias="BUFFER_SCHEDULING_MODE")
    # Tipo do post no Instagram: post | story | reel
    buffer_instagram_post_type: str = Field("post", alias="BUFFER_INSTAGRAM_POST_TYPE")

    # Hospedagem de imagens (Buffer exige URL pública). Backend: "cloudinary" | "none"
    image_host_backend: str = Field("cloudinary", alias="IMAGE_HOST_BACKEND")
    cloudinary_cloud_name: str = Field("", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field("", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field("", alias="CLOUDINARY_API_SECRET")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: int = Field(..., alias="TELEGRAM_CHAT_ID")
    telegram_approval_timeout: int = Field(7200, alias="TELEGRAM_APPROVAL_TIMEOUT")

    # Scheduler
    scheduler_timezone: str = Field("America/Sao_Paulo", alias="SCHEDULER_TIMEZONE")
    scheduler_enabled: bool = Field(True, alias="SCHEDULER_ENABLED")
    # Espera entre tentativas de um job que falhou (backoff fixo, em segundos).
    scheduler_retry_delay_seconds: int = Field(300, alias="SCHEDULER_RETRY_DELAY_SECONDS")

    # Storage
    db_path: Path = Field(Path("./data/db/agent.db"), alias="DB_PATH")

    # Briefing semanal (HU-BACKEND-06). Fonte do "guia" do Hub — DA-05 ainda em aberto;
    # por ora um JSON local plugável (ver briefing_repository.py).
    briefing_file: Path = Field(Path("./data/briefing.json"), alias="BRIEFING_FILE")
    agent_id: str = Field("impressam", alias="AGENT_ID")

    # General
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    max_images_per_carousel: int = Field(4, alias="MAX_IMAGES_PER_CAROUSEL")
    post_cooldown_minutes: int = Field(30, alias="POST_COOLDOWN_MINUTES")
    max_redo_attempts: int = Field(3, alias="MAX_REDO_ATTEMPTS")
    templates_dir: Path = Field(Path("./data/templates"), alias="TEMPLATES_DIR")
    images_dir: Path = Field(Path("./data/images"), alias="IMAGES_DIR")

    # Criação conversacional (/criar)
    creation_session_timeout: int = Field(1800, alias="CREATION_SESSION_TIMEOUT")
    creation_max_rounds: int = Field(12, alias="CREATION_MAX_ROUNDS")

    # Logo/marca sobreposta via Pillow no pós-processamento (exato, sem custo de API).
    # A IA gera a imagem "limpa"; o logo real é colado por cima aqui.
    logo_enabled: bool = Field(False, alias="LOGO_ENABLED")
    logo_path: Path = Field(Path("./assets/brand/logo.png"), alias="LOGO_PATH")
    # Posição: bottom-right | bottom-left | top-right | top-left
    logo_position: str = Field("bottom-right", alias="LOGO_POSITION")
    # Largura do logo como fração da largura da imagem (0.18 = 18%).
    logo_scale: float = Field(0.18, alias="LOGO_SCALE")
    # Margem em px entre o logo e a borda da imagem.
    logo_margin: int = Field(48, alias="LOGO_MARGIN")
    # Opacidade do logo (0.0 transparente … 1.0 opaco).
    logo_opacity: float = Field(0.9, alias="LOGO_OPACITY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
