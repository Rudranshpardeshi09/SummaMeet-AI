"""Celery application instance for the transcription worker."""

from __future__ import annotations

from celery import Celery

from transcription_worker.config import get_settings

settings = get_settings()

celery_app = Celery(
    "transcription_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Task routing — transcription tasks go to the 'transcription' queue
    task_routes={
        "transcription_worker.tasks.*": {"queue": "transcription"},
    },
    # Limited concurrency (heavy compute tasks)
    worker_concurrency=1,
    # Prefetch one task at a time
    worker_prefetch_multiplier=1,
    # Acknowledge after task completes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Long task time limit (transcription can take a while)
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 min soft limit
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks module
celery_app.autodiscover_tasks(["transcription_worker"])
