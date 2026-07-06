import json
from typing import Any
import structlog
from redis.asyncio import Redis

from app.core.config import get_settings

logger = structlog.get_logger("pubsub")
settings = get_settings()

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

async def publish_meeting_event(meeting_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Publish a real-time event for a specific meeting to a Redis channel."""
    channel = f"meeting:{meeting_id}"
    message = {
        "type": event_type,
        "payload": payload
    }
    
    try:
        await redis_client.publish(channel, json.dumps(message))
        logger.debug("Published event", channel=channel, event_type=event_type)
    except Exception as e:
        logger.error("Failed to publish event", channel=channel, error=str(e))
