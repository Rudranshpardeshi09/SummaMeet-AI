"""Application configuration via pydantic-settings.

Reads from .env file and environment variables. All config is validated
at startup — the app crashes fast if required values are missing.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_name: str = "ai-video-note-taker"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"

    # ---- FastAPI ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:8001", "http://localhost:3000"]

    # ---- PostgreSQL ----
    database_url: str = "postgresql+asyncpg://notetaker:notetaker_dev_password@localhost:5432/ai_note_taker"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- JWT ----
    jwt_private_key_path: str = "./jwt_keys/jwt_private.pem"
    jwt_public_key_path: str = "./jwt_keys/jwt_public.pem"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "RS256"

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_audio: str = "audio-chunks"
    minio_bucket_reports: str = "report-artifacts"
    minio_use_ssl: bool = False

    # ---- Celery ----
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ---- Encryption ----
    fernet_encryption_key: str = "change-me-generate-a-real-fernet-key"

    # ---- Rate Limiting ----
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "10/minute"

    # ---- Seed Data ----
    seed_admin_email: str = "admin@company.com"
    seed_admin_password: str = "admin123456"
    seed_org_name: str = "Default Organization"
    seed_org_slug: str = "default-org"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
