from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "api_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scheduler"]
)

# Optional configuration, see the application user guide.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Route 'bot_worker.tasks.*' to the 'bot' queue
    task_routes={
        "bot_worker.tasks.*": {"queue": "bot"},
        "transcription_worker.tasks.*": {"queue": "transcription"},
    },
)

# Celery beat schedule for checking upcoming meetings
celery_app.conf.beat_schedule = {
    "schedule-upcoming-meetings-every-minute": {
        "task": "app.tasks.scheduler.schedule_upcoming_meetings",
        "schedule": 60.0,  # Every 60 seconds
    },
}
