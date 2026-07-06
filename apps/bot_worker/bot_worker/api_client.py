"""HTTP client for bot worker → API communication.

All calls include X-API-Key header for service-to-service authentication.
Includes retry logic with exponential backoff.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bot_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BotAPIClient:
    """HTTP client for the bot worker to communicate with the FastAPI backend."""

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
            timeout=httpx.Timeout(30.0, connect=10.0),
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
                    wait = 2 ** attempt  # 1s, 2s, 4s
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

    def create_bot_session(
        self, meeting_id: str, worker_node: str | None = None
    ) -> dict:
        """Create a new bot session for a meeting."""
        resp = self._request(
            "POST",
            "/api/v1/internal/bot/sessions",
            json={"meeting_id": meeting_id, "worker_node": worker_node},
        )
        return resp.json()

    def update_session_status(
        self,
        session_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> dict:
        """Update bot session status."""
        payload: dict[str, Any] = {"status": status}
        if failure_reason:
            payload["failure_reason"] = failure_reason

        resp = self._request(
            "PATCH",
            f"/api/v1/internal/bot/sessions/{session_id}/status",
            json=payload,
        )
        return resp.json()

    def get_session(self, session_id: str) -> dict:
        """Get bot session details."""
        resp = self._request("GET", f"/api/v1/internal/bot/sessions/{session_id}")
        return resp.json()

    def log_event(
        self,
        session_id: str,
        event_type: str,
        details: dict | None = None,
    ) -> dict:
        """Append an event to the session's raw event log."""
        resp = self._request(
            "POST",
            f"/api/v1/internal/bot/sessions/{session_id}/events",
            json={"event_type": event_type, "details": details or {}},
        )
        return resp.json()

    def update_meeting_status(
        self, meeting_id: str, status: str
    ) -> dict:
        """Update the meeting status."""
        resp = self._request(
            "PATCH",
            f"/api/v1/internal/meetings/{meeting_id}/status",
            json={"status": status},
        )
        return resp.json()

    def register_audio_chunk(
        self,
        session_id: str,
        chunk_index: int,
        minio_key: str,
        duration_ms: int,
        size_bytes: int,
        fmt: str = "webm",
    ) -> dict:
        """Register an uploaded audio chunk."""
        resp = self._request(
            "POST",
            f"/api/v1/internal/bot/sessions/{session_id}/audio-chunks",
            json={
                "chunk_index": chunk_index,
                "minio_key": minio_key,
                "duration_ms": duration_ms,
                "size_bytes": size_bytes,
                "format": fmt,
            },
        )
        return resp.json()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> BotAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
