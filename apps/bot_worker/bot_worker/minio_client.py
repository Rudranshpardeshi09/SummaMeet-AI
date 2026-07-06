"""MinIO client for uploading audio chunks from the bot worker."""

from __future__ import annotations

import logging
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from bot_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MinIOUploader:
    """Upload audio chunks to MinIO (S3-compatible) object storage."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
        use_ssl: bool | None = None,
    ) -> None:
        self._endpoint = endpoint or settings.minio_endpoint
        self._access_key = access_key or settings.minio_access_key
        self._secret_key = secret_key or settings.minio_secret_key
        self._bucket_name = bucket_name or settings.minio_bucket_audio
        self._use_ssl = use_ssl if use_ssl is not None else settings.minio_use_ssl

        self._client = Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._use_ssl,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the audio bucket if it doesn't exist."""
        try:
            if not self._client.bucket_exists(self._bucket_name):
                self._client.make_bucket(self._bucket_name)
                logger.info("Created MinIO bucket: %s", self._bucket_name)
        except S3Error as e:
            logger.error("Failed to check/create bucket: %s", e)
            raise

    def upload_chunk(
        self,
        local_path: Path,
        meeting_id: str,
        session_id: str,
        chunk_index: int,
    ) -> str:
        """Upload an audio chunk file to MinIO.

        Args:
            local_path: Path to the local audio file.
            meeting_id: Meeting UUID.
            session_id: Bot session UUID.
            chunk_index: Ordered chunk index (0-based).

        Returns:
            The MinIO object key (path) where the chunk was stored.
        """
        ext = local_path.suffix or ".webm"
        object_key = (
            f"{meeting_id}/{session_id}/chunk_{chunk_index:04d}{ext}"
        )

        file_size = local_path.stat().st_size

        with open(local_path, "rb") as f:
            self._client.put_object(
                bucket_name=self._bucket_name,
                object_name=object_key,
                data=f,
                length=file_size,
                content_type=f"audio/{ext.lstrip('.')}",
            )

        logger.info(
            "Uploaded chunk %d to %s/%s (%d bytes)",
            chunk_index,
            self._bucket_name,
            object_key,
            file_size,
        )
        return object_key
