"""MinIO client for downloading audio chunks in the transcription worker."""

from __future__ import annotations

import logging
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from transcription_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MinIODownloader:
    """Download audio chunks from MinIO for transcription processing."""

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

    def download_chunk(self, minio_key: str, local_dir: Path) -> Path:
        """Download an audio chunk from MinIO to a local directory.

        Args:
            minio_key: Object key in MinIO (e.g., "meeting_id/session_id/chunk_0000.webm").
            local_dir: Directory to save the downloaded file.

        Returns:
            Path to the downloaded file.
        """
        local_dir.mkdir(parents=True, exist_ok=True)
        filename = minio_key.split("/")[-1]
        local_path = local_dir / filename

        try:
            self._client.fget_object(
                bucket_name=self._bucket_name,
                object_name=minio_key,
                file_path=str(local_path),
            )
            logger.info(
                "Downloaded %s/%s → %s",
                self._bucket_name,
                minio_key,
                local_path,
            )
            return local_path

        except S3Error as e:
            logger.error("Failed to download %s: %s", minio_key, e)
            raise

    def list_chunks(
        self, meeting_id: str, session_id: str
    ) -> list[str]:
        """List all audio chunk keys for a meeting/session.

        Returns:
            Sorted list of MinIO object keys.
        """
        prefix = f"{meeting_id}/{session_id}/"
        objects = self._client.list_objects(
            self._bucket_name,
            prefix=prefix,
            recursive=True,
        )
        keys = sorted(obj.object_name for obj in objects if obj.object_name)
        logger.info(
            "Found %d chunks for session %s",
            len(keys),
            session_id,
        )
        return keys
