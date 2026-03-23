"""
app/config.py — Application settings loaded from environment variables.

Uses pydantic-settings so every value is validated at startup.
All secrets come from env vars or the .env file — never hardcoded.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    app_log_level: str = "INFO"
    api_key: str = Field(..., description="Admin API key for X-API-Key header")

    # ── Database ──────────────────────────────────────────────
    postgres_user: str = "golav"
    postgres_password: str = "golav_secret"
    postgres_db: str = "golav"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        import os
        # Railway (and some other PaaS) inject DATABASE_URL as postgres:// which asyncpg rejects
        raw = os.getenv("DATABASE_URL", "")
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql+asyncpg://", 1)
        if raw.startswith("postgresql+asyncpg://"):
            return raw
        # Fall back to individual components
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Redis ─────────────────────────────────────────────────
    redis_password: str = "redis_secret"
    redis_host: str = "redis"
    redis_port: int = 6379

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    @computed_field  # type: ignore[misc]
    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @computed_field  # type: ignore[misc]
    @property
    def celery_result_backend(self) -> str:
        return self.redis_url

    # ── Twilio ────────────────────────────────────────────────
    twilio_account_sid: str = Field(..., description="Twilio Account SID")
    twilio_auth_token: str = Field(..., description="Twilio Auth Token")
    twilio_whatsapp_from: str = Field(..., description="Twilio WhatsApp sender e.g. whatsapp:+212XXXXXXXXX")

    # ── OpenAI ────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 1024
    openai_temperature: float = 0.3

    # ── Booking ───────────────────────────────────────────────
    slot_duration_minutes: int = 60
    slot_hold_ttl_minutes: int = 10
    business_hours_start: int = 8    # 08:00 Africa/Casablanca
    business_hours_end: int = 18     # 18:00 Africa/Casablanca
    max_advance_booking_days: int = 14

    # ── AI ────────────────────────────────────────────────────
    ai_confidence_threshold: float = 0.6
    ai_max_retries: int = 2

    # ── Outbox ────────────────────────────────────────────────
    outbox_max_retries: int = 5
    outbox_retry_backoff_base: int = 60  # seconds

    # ── Rate limiting ─────────────────────────────────────────
    rate_limit_per_customer_per_minute: int = 10

    # ── Export ────────────────────────────────────────────────
    export_dir: str = "/app/exports"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import and call this everywhere."""
    return Settings()


settings = get_settings()
