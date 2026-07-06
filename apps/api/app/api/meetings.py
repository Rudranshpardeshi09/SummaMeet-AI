"""Meetings API routes — CRUD and internal status updates."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_auth import ValidApiKey
from app.core.pubsub import publish_meeting_event
from app.core.celery import celery_app
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.meeting import Meeting
from app.models.project import Project
from app.models.bot_session import BotSession
from app.models.meeting_participant import MeetingParticipant
from app.schemas.meeting import (
    UpdateMeetingStatusRequest, 
    MeetingCreate, 
    MeetingUpdate, 
    MeetingResponse
)
from app.schemas.pagination import PaginatedResponse
from app.core.pagination import encode_cursor, decode_cursor
from app.core.errors import NotFoundError, ForbiddenError
from app.core.audit import log_audit_event

router = APIRouter(tags=["Meetings"])


# --- Internal Worker Endpoints ---

_VALID_MEETING_TRANSITIONS: dict[str, set[str]] = {
    "SCHEDULED": {"BOT_STARTING", "CANCELLED", "FAILED"},
    "BOT_STARTING": {"WAITING_FOR_ADMISSION", "IN_PROGRESS", "FAILED", "CANCELLED"},
    "WAITING_FOR_ADMISSION": {"IN_PROGRESS", "FAILED", "CANCELLED"},
    "IN_PROGRESS": {"PROCESSING_TRANSCRIPT", "FAILED", "CANCELLED"},
    "PROCESSING_TRANSCRIPT": {"GENERATING_REPORT", "FAILED"},
    "GENERATING_REPORT": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

@router.patch(
    "/internal/meetings/{meeting_id}/status",
    status_code=status.HTTP_200_OK,
    tags=["Meetings (Internal)"]
)
async def update_meeting_status(
    meeting_id: uuid.UUID,
    body: UpdateMeetingStatusRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update meeting status from workers."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found",
        )

    allowed = _VALID_MEETING_TRANSITIONS.get(meeting.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition: {meeting.status} → {body.status}. "
                f"Allowed: {', '.join(sorted(allowed)) or 'none (terminal state)'}"
            ),
        )

    meeting.status = body.status
    await db.flush()

    # Broadcast status change
    await publish_meeting_event(
        meeting_id=str(meeting.id),
        event_type="MEETING_STATUS_UPDATED",
        payload={"status": meeting.status}
    )

    # Orchestrate next pipeline step
    if meeting.status == "PROCESSING_TRANSCRIPT":
        # Find latest bot session for this meeting
        bot_session_stmt = select(BotSession).where(BotSession.meeting_id == meeting.id).order_by(desc(BotSession.created_at)).limit(1)
        res = await db.execute(bot_session_stmt)
        latest_session = res.scalar_one_or_none()
        if latest_session:
            celery_app.send_task(
                "transcription_worker.tasks.transcribe_meeting",
                args=[str(meeting.id), str(latest_session.id)],
                queue="transcription"
            )
            
    elif meeting.status == "GENERATING_REPORT":
        celery_app.send_task(
            "summarization_worker.tasks.generate_report",
            args=[str(meeting.id)],
            queue="summarization"
        )

    await db.commit()

    return {
        "id": str(meeting.id),
        "status": meeting.status,
        "previous_status": body.status,
    }

# --- User-Facing Endpoints ---

@router.get("/meetings", response_model=PaginatedResponse[MeetingResponse])
async def list_meetings(
    project_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List meetings with cursor pagination."""
    stmt = select(Meeting).options(selectinload(Meeting.participants)).where(
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    if project_id:
        stmt = stmt.where(Meeting.project_id == project_id)

    if cursor:
        decoded_cursor = decode_cursor(cursor, is_datetime=True)
        if decoded_cursor:
            stmt = stmt.where(Meeting.created_at < decoded_cursor)

    stmt = stmt.order_by(desc(Meeting.created_at)).limit(limit + 1)
    
    result = await db.execute(stmt)
    meetings = result.scalars().all()

    has_more = len(meetings) > limit
    if has_more:
        meetings = meetings[:limit]

    next_cursor = encode_cursor(meetings[-1].created_at) if meetings else None

    return PaginatedResponse(
        data=meetings,
        next_cursor=next_cursor,
        has_more=has_more
    )

@router.post("/meetings", response_model=MeetingResponse)
async def create_meeting(
    meeting_in: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new meeting."""
    project_id = meeting_in.project_id
    if not project_id:
        stmt = select(Project).where(Project.organization_id == current_user.organization_id).limit(1)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            project = Project(
                organization_id=current_user.organization_id,
                name="General",
                created_by=current_user.id
            )
            db.add(project)
            await db.flush()
        project_id = project.id

    new_meeting = Meeting(
        organization_id=current_user.organization_id,
        project_id=project_id,
        host_user_id=current_user.id,
        created_by=current_user.id,
        title=meeting_in.title,
        notes=meeting_in.description,
        meeting_url=meeting_in.meeting_url,
        scheduled_start_time=meeting_in.scheduled_at or datetime.now(UTC),
        status="SCHEDULED",
    )
    db.add(new_meeting)
    await db.flush()

    # Link participants
    if meeting_in.participants:
        for p in meeting_in.participants:
            mp = MeetingParticipant(
                meeting_id=new_meeting.id,
                user_id=p.user_id,
                role=p.role
            )
            db.add(mp)
        await db.flush()

    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="CREATE",
        entity_type="Meeting",
        entity_id=new_meeting.id,
        changes={"title": new_meeting.title}
    )
    
    await db.commit()
    await db.refresh(new_meeting)
    return new_meeting

@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific meeting by ID."""
    stmt = select(Meeting).options(selectinload(Meeting.participants)).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    return meeting

@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: uuid.UUID,
    meeting_in: MeetingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a meeting."""
    stmt = select(Meeting).options(selectinload(Meeting.participants)).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    changes = {}
    for field, value in meeting_in.model_dump(exclude_unset=True).items():
        old_val = getattr(meeting, field)
        if old_val != value:
            changes[field] = {"old": old_val, "new": value}
            setattr(meeting, field, value)

    if changes:
        await log_audit_event(
            session=db,
            actor_id=current_user.id,
            organization_id=current_user.organization_id,
            action="UPDATE",
            entity_type="Meeting",
            entity_id=meeting.id,
            changes=changes
        )
        await db.commit()
        await db.refresh(meeting)

    return meeting

@router.delete("/meetings/{meeting_id}")
async def delete_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete/cancel a meeting."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    meeting.deleted_at = datetime.now(UTC)
    meeting.status = "CANCELLED"
    
    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="DELETE",
        entity_type="Meeting",
        entity_id=meeting.id
    )
    
    await db.commit()
    return {"message": "Meeting deleted successfully"}

@router.post("/meetings/{meeting_id}/start-bot")
async def start_bot(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually start the bot for a meeting."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    if meeting.status not in ["SCHEDULED", "FAILED", "CANCELLED", "COMPLETED", "GENERATING_REPORT"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot start bot when meeting is in {meeting.status} status"
        )

    # Create BotSession
    bot_session = BotSession(
        meeting_id=meeting.id,
        status="QUEUED"
    )
    db.add(bot_session)

    meeting.status = "BOT_STARTING"
    
    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="START_BOT",
        entity_type="Meeting",
        entity_id=meeting.id
    )

    await db.commit()
    await db.refresh(bot_session)

    # Dispatch celery task
    celery_app.send_task(
        "bot_worker.tasks.join_meeting",
        args=[str(meeting.id), meeting.meeting_url, str(bot_session.id)],
        queue="bot"
    )

    await publish_meeting_event(
        meeting_id=str(meeting.id),
        event_type="MEETING_STATUS_UPDATED",
        payload={"status": meeting.status}
    )

    return {"message": "Bot starting"}

@router.post("/meetings/{meeting_id}/stop-bot")
async def stop_bot(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually stop the bot for a meeting."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    if meeting.status in ["COMPLETED", "FAILED", "CANCELLED", "SCHEDULED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot stop bot when meeting is in {meeting.status} status"
        )

    meeting.status = "CANCELLED"

    # Also update any active bot sessions to FAILED so the celery worker stops retrying
    stmt = select(BotSession).where(
        BotSession.meeting_id == meeting.id,
        BotSession.status.in_(["QUEUED", "JOINING", "WAITING_FOR_ADMISSION", "JOINED", "RECORDING"])
    )
    result = await db.execute(stmt)
    active_sessions = result.scalars().all()
    for session in active_sessions:
        session.status = "FAILED"
        session.failure_reason = "Manually stopped by user"

    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="STOP_BOT",
        entity_type="Meeting",
        entity_id=meeting.id
    )

    await db.commit()

    await publish_meeting_event(
        meeting_id=str(meeting.id),
        event_type="BOT_STOP_REQUESTED",
        payload={}
    )
    
    await publish_meeting_event(
        meeting_id=str(meeting.id),
        event_type="MEETING_STATUS_UPDATED",
        payload={"status": meeting.status}
    )

    return {"message": "Bot stop requested"}
