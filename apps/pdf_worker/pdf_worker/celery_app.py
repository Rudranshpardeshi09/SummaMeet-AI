import os
from celery import Celery
import structlog

logger = structlog.get_logger("pdf_worker")

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6380/1")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6380/2")

celery_app = Celery(
    "pdf_worker",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["pdf_worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "pdf_worker.tasks.*": {"queue": "pdf_generation"}
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

logger.info("Initialized PDF Celery worker", broker=BROKER_URL)
