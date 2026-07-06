"""Celery tasks for the bot worker.

Defines the `join_meeting` task that orchestrates the full bot lifecycle:
browser launch → join → record → cleanup.
Supports multiple platforms (Google Meet, Jitsi) via URL-based detection.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from celery import Task

from bot_worker.api_client import BotAPIClient
from bot_worker.base_bot import BaseMeetingBot
from bot_worker.celery_app import celery_app
from bot_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def create_bot(
    meeting_url: str,
    meeting_id: str,
    session_id: str,
    api_client: BotAPIClient,
) -> BaseMeetingBot:
    """Factory: create the correct bot based on the meeting URL.

    Args:
        meeting_url: The meeting URL (Google Meet, Jitsi, etc.).
        meeting_id: UUID of the meeting.
        session_id: UUID of the bot session.
        api_client: API client for status updates.

    Returns:
        An instance of the appropriate bot subclass.

    Raises:
        ValueError: If the platform cannot be determined from the URL.
    """
    parsed = urlparse(meeting_url)
    host = (parsed.hostname or "").lower()

    # Google Meet
    if "meet.google.com" in host:
        from bot_worker.meet_bot import GoogleMeetBot
        return GoogleMeetBot(
            meeting_url=meeting_url,
            meeting_id=meeting_id,
            session_id=session_id,
            api_client=api_client,
        )

    # Jitsi Meet (public or self-hosted)
    jitsi_domain = settings.jitsi_domain.lower()
    if jitsi_domain in host or "jitsi" in host or "8x8.vc" in host:
        from bot_worker.jitsi_bot import JitsiMeetBot
        return JitsiMeetBot(
            meeting_url=meeting_url,
            meeting_id=meeting_id,
            session_id=session_id,
            api_client=api_client,
        )

    raise ValueError(
        f"Unsupported meeting platform: {host}. "
        "Supported platforms: Google Meet (meet.google.com), "
        f"Jitsi Meet ({jitsi_domain})"
    )


@celery_app.task(
    bind=True,
    name="bot_worker.tasks.join_meeting",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
    default_retry_delay=30,
)
def join_meeting(
    self: Task,
    meeting_id: str,
    meeting_url: str,
    session_id: str,
) -> dict:
    """Join a meeting, capture audio, and report status.

    Supports Google Meet and Jitsi Meet. The platform is auto-detected
    from the meeting_url.

    Args:
        meeting_id: UUID of the meeting to join.
        meeting_url: Meeting URL (Google Meet or Jitsi).
        session_id: UUID of the pre-created bot session.

    Returns:
        Dict with session_id and final status.

    Retries:
        Up to 3 times with exponential backoff (30s, 120s, 300s).
    """
    logger.info(
        "Starting bot task for meeting %s (session %s, attempt %d/%d)",
        meeting_id,
        session_id,
        (self.request.retries or 0) + 1,
        (self.max_retries or 0) + 1,
    )

    with BotAPIClient() as api_client:
        try:
            # Check if session is still active before starting
            try:
                session_info = api_client.get_session(session_id)
                if session_info.get("status") in ["FAILED", "ENDED", "CANCELLED"]:
                    logger.warning("Session %s is already in terminal state (%s), aborting task.", session_id, session_info.get("status"))
                    return {"session_id": session_id, "meeting_id": meeting_id, "status": "ABORTED"}
            except Exception as e:
                logger.warning("Failed to check session status before starting: %s", str(e))

            bot = create_bot(
                meeting_url=meeting_url,
                meeting_id=meeting_id,
                session_id=session_id,
                api_client=api_client,
            )
            logger.info("Created %s bot for URL: %s", bot.PLATFORM_NAME, meeting_url)
            bot.run()

            return {
                "session_id": session_id,
                "meeting_id": meeting_id,
                "status": "ENDED",
            }

        except Exception as exc:
            # Check if session was manually cancelled during execution
            try:
                session_info = api_client.get_session(session_id)
                if session_info.get("status") in ["FAILED", "ENDED", "CANCELLED"]:
                    logger.warning("Session %s was manually cancelled, aborting retries.", session_id)
                    return {"session_id": session_id, "meeting_id": meeting_id, "status": "ABORTED"}
            except Exception:
                pass

            retries_left = (self.max_retries or 0) - (self.request.retries or 0)

            if retries_left > 0:
                # Exponential backoff: 30s, 120s, 300s
                countdown = 30 * (2 ** (self.request.retries or 0))
                logger.warning(
                    "Bot task failed, retrying in %ds (%d retries left): %s",
                    countdown,
                    retries_left,
                    str(exc),
                )
                raise self.retry(exc=exc, countdown=countdown)
            else:
                # Final failure — mark as FAILED
                logger.error(
                    "Bot task failed permanently after %d retries: %s",
                    self.max_retries,
                    str(exc),
                )
                try:
                    api_client.update_session_status(
                        session_id, "FAILED", failure_reason=str(exc)
                    )
                    api_client.update_meeting_status(meeting_id, "FAILED")
                except Exception:
                    logger.exception("Failed to mark session/meeting as FAILED")

                return {
                    "session_id": session_id,
                    "meeting_id": meeting_id,
                    "status": "FAILED",
                    "error": str(exc),
                }
