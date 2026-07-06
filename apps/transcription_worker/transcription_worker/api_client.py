"""HTTP client for transcription worker → API communication."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from transcription_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TranscriptionAPIClient:
    """HTTP client for the transcription worker to communicate with the FastAPI backend."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
    ) -> None:
        self._base_url = (base_url or settings.api_base_url).rstrip("/")
        self._api_key = api_key or settings.bot_api_key
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with retry and exponential backoff."""
        import time

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "API request failed (attempt %d/%d), retrying in %ds: %s %s → %s",
                        attempt + 1,
                        self._max_retries,
                        wait,
                        method,
                        path,
                        str(e),
                    )
                    time.sleep(wait)

        logger.error(
            "API request failed after %d attempts: %s %s",
            self._max_retries,
            method,
            path,
        )
        raise last_error  # type: ignore[misc]

    def get_audio_chunks(self, session_id: str) -> list[dict]:
        """Get ordered audio chunks for a bot session."""
        resp = self._request(
            "GET",
            f"/api/v1/internal/bot/sessions/{session_id}/audio-chunks",
        )
        return resp.json()

    def create_transcript_segments_batch(
        self,
        meeting_id: str,
        bot_session_id: str,
        segments: list[dict],
    ) -> dict:
        """Batch create transcript segments."""
        resp = self._request(
            "POST",
            "/api/v1/internal/transcripts/segments/batch",
            json={
                "meeting_id": meeting_id,
                "bot_session_id": bot_session_id,
                "segments": segments,
            },
        )
        return resp.json()

    def update_meeting_status(self, meeting_id: str, status: str) -> dict:
        """Update meeting status."""
        resp = self._request(
            "PATCH",
            f"/api/v1/internal/meetings/{meeting_id}/status",
            json={"status": status},
        )
        return resp.json()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> TranscriptionAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
