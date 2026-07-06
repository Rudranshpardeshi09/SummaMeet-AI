"""Bot session internal API routes — called by bot worker via API key auth.

These endpoints allow the bot worker to create sessions, report status changes,
log events, and register uploaded audio chunks. All protected by X-API-Key.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_auth import ValidApiKey
from app.db.session import get_db
from app.models.audio_chunk import AudioChunk
from app.models.bot_session import BotSession
from app.schemas.bot import (
    AudioChunkResponse,
    BotEventRequest,
    BotSessionResponse,
    CreateBotSessionRequest,
    RegisterAudioChunkRequest,
    UpdateBotStatusRequest,
)

router = APIRouter(prefix="/internal/bot", tags=["Bot (Internal)"])


# Valid status transitions for bot sessions
_VALID_BOT_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"JOINING", "FAILED"},
    "JOINING": {"WAITING_FOR_ADMISSION", "JOINED", "FAILED"},
    "WAITING_FOR_ADMISSION": {"JOINED", "FAILED"},
    "JOINED": {"RECORDING", "ENDED", "FAILED"},
    "RECORDING": {"ENDED", "FAILED"},
    "ENDED": set(),
    "FAILED": set(),
}


@router.post(
    "/sessions",
    response_model=BotSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bot_session(
    body: CreateBotSessionRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new bot session for a meeting."""
    session = BotSession(
        meeting_id=uuid.UUID(body.meeting_id),
        status="QUEUED",
        worker_node=body.worker_node,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return BotSessionResponse(
        id=str(session.id),
        meeting_id=str(session.meeting_id),
        status=session.status,
        worker_node=session.worker_node,
        join_attempted_at=session.join_attempted_at,
        joined_at=session.joined_at,
        ended_at=session.ended_at,
        failure_reason=session.failure_reason,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=BotSessionResponse,
)
async def get_bot_session(
    session_id: uuid.UUID,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get bot session details."""
    stmt = select(BotSession).where(BotSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot session {session_id} not found",
        )

    return BotSessionResponse(
        id=str(session.id),
        meeting_id=str(session.meeting_id),
        status=session.status,
        worker_node=session.worker_node,
        join_attempted_at=session.join_attempted_at,
        joined_at=session.joined_at,
        ended_at=session.ended_at,
        failure_reason=session.failure_reason,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.patch(
    "/sessions/{session_id}/status",
    response_model=BotSessionResponse,
)
async def update_bot_session_status(
    session_id: uuid.UUID,
    body: UpdateBotStatusRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update bot session status with FSM transition validation."""
    stmt = select(BotSession).where(BotSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot session {session_id} not found",
        )

    # Validate status transition
    allowed = _VALID_BOT_TRANSITIONS.get(session.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition: {session.status} → {body.status}. "
                f"Allowed: {', '.join(sorted(allowed)) or 'none (terminal state)'}"
            ),
        )

    now = datetime.now(UTC)
    session.status = body.status

    # Set timestamp fields based on status
    if body.status == "JOINING":
        session.join_attempted_at = now
    elif body.status == "JOINED":
        session.joined_at = now
    elif body.status in ("ENDED", "FAILED"):
        session.ended_at = now
        if body.failure_reason:
            session.failure_reason = body.failure_reason

    await db.flush()
    await db.refresh(session)

    return BotSessionResponse(
        id=str(session.id),
        meeting_id=str(session.meeting_id),
        status=session.status,
        worker_node=session.worker_node,
        join_attempted_at=session.join_attempted_at,
        joined_at=session.joined_at,
        ended_at=session.ended_at,
        failure_reason=session.failure_reason,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/sessions/{session_id}/events",
    status_code=status.HTTP_201_CREATED,
)
async def log_bot_event(
    session_id: uuid.UUID,
    body: BotEventRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Append an event entry to the bot session's raw event log."""
    stmt = select(BotSession).where(BotSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot session {session_id} not found",
        )

    # Append event to the JSONB event log
    event_entry = {
        "event_type": body.event_type,
        "details": body.details or {},
        "timestamp": (body.timestamp or datetime.now(UTC)).isoformat(),
    }

    current_log = session.raw_event_log or []
    current_log.append(event_entry)
    # Force SQLAlchemy to detect the JSONB mutation
    session.raw_event_log = list(current_log)

    await db.flush()

    return {"status": "ok", "event_count": len(session.raw_event_log)}


@router.post(
    "/sessions/{session_id}/audio-chunks",
    response_model=AudioChunkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_audio_chunk(
    session_id: uuid.UUID,
    body: RegisterAudioChunkRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register an uploaded audio chunk for a bot session."""
    # Verify session exists and get meeting_id
    stmt = select(BotSession).where(BotSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot session {session_id} not found",
        )

    chunk = AudioChunk(
        bot_session_id=session_id,
        meeting_id=session.meeting_id,
        chunk_index=body.chunk_index,
        minio_key=body.minio_key,
        duration_ms=body.duration_ms,
        size_bytes=body.size_bytes,
        format=body.format,
    )
    db.add(chunk)
    await db.flush()
    await db.refresh(chunk)

    return AudioChunkResponse(
        id=str(chunk.id),
        bot_session_id=str(chunk.bot_session_id),
        meeting_id=str(chunk.meeting_id),
        chunk_index=chunk.chunk_index,
        minio_key=chunk.minio_key,
        duration_ms=chunk.duration_ms,
        size_bytes=chunk.size_bytes,
        format=chunk.format,
        created_at=chunk.created_at,
    )
