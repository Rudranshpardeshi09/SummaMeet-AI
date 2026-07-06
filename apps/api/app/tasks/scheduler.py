import asyncio
import structlog
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, and_

from app.core.celery import celery_app
from app.db.session import async_session_factory
from app.models.meeting import Meeting
from app.models.bot_session import BotSession

logger = structlog.get_logger("api_scheduler")

async def _schedule_upcoming_meetings():
    """Async logic to fetch and schedule upcoming meetings."""
    now = datetime.now(UTC)
    five_mins_from_now = now + timedelta(minutes=5)
    
    async with async_session_factory() as session:
        # Find meetings that are SCHEDULED and starting within the next 5 mins
        stmt = select(Meeting).where(
            and_(
                Meeting.status == "SCHEDULED",
                Meeting.scheduled_at <= five_mins_from_now,
                Meeting.scheduled_at >= now - timedelta(minutes=30), # Don't schedule old missed meetings indefinitely
                Meeting.deleted_at.is_(None)
            )
        )
        result = await session.execute(stmt)
        upcoming_meetings = result.scalars().all()
        
        for meeting in upcoming_meetings:
            logger.info("Found upcoming meeting to schedule", meeting_id=str(meeting.id))
            
            # Create a bot session for this meeting
            bot_session = BotSession(
                meeting_id=meeting.id,
                status="QUEUED"
            )
            session.add(bot_session)
            
            # Transition meeting to BOT_STARTING
            meeting.status = "BOT_STARTING"
            
            await session.commit()
            await session.refresh(bot_session)
            
            # Dispatch to bot worker queue
            # Celery uses send_task to send tasks across different codebases
            celery_app.send_task(
                "bot_worker.tasks.join_meeting",
                args=[str(meeting.id), meeting.meeting_url, str(bot_session.id)],
                queue="bot"
            )
            
            logger.info("Dispatched bot worker task", meeting_id=str(meeting.id), bot_session_id=str(bot_session.id))


@celery_app.task(bind=True, name="app.tasks.scheduler.schedule_upcoming_meetings")
def schedule_upcoming_meetings(self):
    """
    Celery Beat task to check the database for upcoming meetings
    and dispatch them to the bot worker.
    """
    logger.info("Running scheduler for upcoming meetings")
    asyncio.run(_schedule_upcoming_meetings())
