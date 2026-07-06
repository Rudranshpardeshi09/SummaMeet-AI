"""Celery application instance for the bot worker."""

from __future__ import annotations

from celery import Celery

from bot_worker.config import get_settings

settings = get_settings()

celery_app = Celery(
    "bot_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Task routing — bot tasks go to the 'bot' queue
    task_routes={
        "bot_worker.tasks.*": {"queue": "bot"},
    },
    # Only one browser per worker process
    worker_concurrency=1,
    # Prefetch one task at a time (heavy tasks)
    worker_prefetch_multiplier=1,
    # Acknowledge after task completes (for failure recovery)
    task_acks_late=True,
    # Reject on worker lost (don't lose tasks)
    task_reject_on_worker_lost=True,
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks module
celery_app.autodiscover_tasks(["bot_worker"])
