import os
from dotenv import load_dotenv
load_dotenv("../../.env")
from celery import Celery
import structlog

logger = structlog.get_logger("summarization_worker")

# Get settings directly from environment or use defaults
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6380/1")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6380/2")

celery_app = Celery(
    "summarization_worker",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["summarization_worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "summarization_worker.tasks.*": {"queue": "summarization"}
    },
    # Ensure tasks are acknowledged only after completion
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

logger.info("Initialized summarization Celery worker", broker=BROKER_URL)
