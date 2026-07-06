"""Transcription worker configuration via pydantic-settings."""

from __future__ import annotations

import shutil
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TranscriptionSettings(BaseSettings):
    """Configuration for the transcription worker process."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
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

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_audio: str = "audio-chunks"
    minio_use_ssl: bool = False

    # ---- Whisper ----
    whisper_model_size: str = "small"  # tiny, base, small, medium, large-v3
    whisper_device: str = "auto"  # auto, cpu, cuda
    whisper_compute_type: str = "auto"  # auto, int8, float16, float32
    whisper_language: str | None = None  # None = auto-detect per segment
    supported_languages: list[str] = ["en", "hi"]

    # ---- Processing ----
    download_dir: str = "./downloads"
    batch_size: int = 50  # Segments per API batch call
    vad_filter: bool = True  # Voice activity detection

    # ---- Logging ----
    log_level: str = "INFO"

    @property
    def resolved_device(self) -> str:
        """Resolve 'auto' to actual device."""
        if self.whisper_device != "auto":
            return self.whisper_device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @property
    def resolved_compute_type(self) -> str:
        """Resolve 'auto' to optimal compute type for the device."""
        if self.whisper_compute_type != "auto":
            return self.whisper_compute_type
        return "float16" if self.resolved_device == "cuda" else "int8"


@lru_cache
def get_settings() -> TranscriptionSettings:
    """Cached singleton settings instance."""
    return TranscriptionSettings()
