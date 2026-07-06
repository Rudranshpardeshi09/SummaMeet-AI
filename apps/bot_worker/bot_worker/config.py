"""Bot worker configuration via pydantic-settings."""

from __future__ import annotations

import platform
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotWorkerSettings(BaseSettings):
    """Configuration for the bot worker process."""

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Celery ----
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ---- API Callback ----
    api_base_url: str = "http://localhost:8000"
    bot_api_key: str = "change-me-to-seeded-bot-api-key"

    # ---- Bot Behavior ----
    lobby_timeout_seconds: int = 600  # 10 minutes
    max_join_retries: int = 3
    headless: bool = False
    bot_display_name: str = "AI Note Taker"

    # ---- Google Auth ----
    use_google_login: bool = False
    google_email: str | None = None
    google_password: str | None = None

    # ---- Jitsi ----
    jitsi_domain: str = "meet.jit.si"

    # ---- Audio Capture ----
    audio_chunk_duration_seconds: int = 30
    recording_dir: str = "./recordings"

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_audio: str = "audio-chunks"
    minio_use_ssl: bool = False

    # ---- Logging ----
    log_level: str = "INFO"

    @property
    def worker_node(self) -> str:
        """Unique identifier for this worker node."""
        return f"bot-{platform.node()}"


@lru_cache
def get_settings() -> BotWorkerSettings:
    """Cached singleton settings instance."""
    return BotWorkerSettings()
