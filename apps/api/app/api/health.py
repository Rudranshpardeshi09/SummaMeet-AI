"""Health check endpoint — reports status of all infrastructure dependencies."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.pubsub import redis_client
from app.core.celery import celery_app

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check system health including database connectivity.

    Returns component-level status for monitoring and load balancers.
    """
    checks = {
        "status": "healthy",
        "components": {},
    }

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["components"]["database"] = {"status": "up"}
    except Exception as e:
        checks["status"] = "degraded"
        checks["components"]["database"] = {
            "status": "down",
            "error": str(e),
        }

    # Redis check
    try:
        await redis_client.ping()
        checks["components"]["redis"] = {"status": "up"}
    except Exception as e:
        checks["status"] = "degraded"
        checks["components"]["redis"] = {
            "status": "down",
            "error": str(e),
        }

    # Celery check
    try:
        # Check if any workers are responding
        ping_res = celery_app.control.ping(timeout=0.5)
        if ping_res:
            checks["components"]["celery"] = {"status": "up", "workers": len(ping_res)}
        else:
            checks["components"]["celery"] = {"status": "degraded", "detail": "No workers responding"}
    except Exception as e:
        checks["status"] = "degraded"
        checks["components"]["celery"] = {
            "status": "down",
            "error": str(e),
        }

    return checks
