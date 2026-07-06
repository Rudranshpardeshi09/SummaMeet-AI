"""Transcript API routes — internal batch creation and user-facing retrieval.

Internal endpoints (X-API-Key auth) for the transcription worker to persist segments.
User-facing endpoints (JWT auth) for reading transcripts.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_auth import ValidApiKey
from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.audio_chunk import AudioChunk
from app.models.transcript_segment import TranscriptSegment
from app.schemas.transcript import (
    AudioChunkInfo,
    BatchCreateSegmentsRequest,
    TranscriptResponse,
    TranscriptSegmentResponse,
)

router = APIRouter(tags=["Transcripts"])


# ---- Internal endpoints (API key auth) ----


@router.post(
    "/api/v1/internal/transcripts/segments/batch",
    status_code=status.HTTP_201_CREATED,
)
async def batch_create_segments(
    body: BatchCreateSegmentsRequest,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Batch create transcript segments (called by transcription worker)."""
    meeting_id = uuid.UUID(body.meeting_id)
    bot_session_id = uuid.UUID(body.bot_session_id)

    created_ids = []
    for seg in body.segments:
        segment = TranscriptSegment(
            meeting_id=meeting_id,
            bot_session_id=bot_session_id,
            sequence_no=seg.sequence_no,
            speaker_label=seg.speaker_label,
            speaker_user_id=uuid.UUID(seg.speaker_user_id) if seg.speaker_user_id else None,
            language=seg.language,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=seg.text,
            confidence=seg.confidence,
        )
        db.add(segment)
        created_ids.append(segment)

    await db.flush()

    return {
        "status": "ok",
        "created_count": len(created_ids),
        "meeting_id": body.meeting_id,
    }


@router.get(
    "/api/v1/internal/bot/sessions/{session_id}/audio-chunks",
    response_model=list[AudioChunkInfo],
)
async def list_audio_chunks(
    session_id: uuid.UUID,
    _api_key: ValidApiKey,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List audio chunks for a bot session, ordered by chunk index."""
    stmt = (
        select(AudioChunk)
        .where(AudioChunk.bot_session_id == session_id)
        .order_by(AudioChunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return [
        AudioChunkInfo(
            chunk_index=c.chunk_index,
            minio_key=c.minio_key,
            duration_ms=c.duration_ms,
            size_bytes=c.size_bytes,
            format=c.format,
        )
        for c in chunks
    ]


# ---- User-facing endpoints (JWT auth) ----


@router.get(
    "/api/v1/meetings/{meeting_id}/transcript",
    response_model=TranscriptResponse,
)
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the full transcript for a meeting.

    Returns all segments ordered by sequence number, plus aggregate metadata.
    """
    stmt = (
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.sequence_no)
    )
    result = await db.execute(stmt)
    segments = result.scalars().all()

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No transcript found for meeting {meeting_id}",
        )

    # Compute aggregates
    speakers = sorted({s.speaker_label for s in segments})
    languages = sorted({s.language for s in segments})
    total_duration_ms = max(s.end_ms for s in segments) - min(s.start_ms for s in segments)

    return TranscriptResponse(
        meeting_id=str(meeting_id),
        total_segments=len(segments),
        total_duration_ms=total_duration_ms,
        speakers=speakers,
        languages=languages,
        segments=[
            TranscriptSegmentResponse(
                id=str(s.id),
                meeting_id=str(s.meeting_id),
                bot_session_id=str(s.bot_session_id),
                sequence_no=s.sequence_no,
                speaker_label=s.speaker_label,
                speaker_user_id=str(s.speaker_user_id) if s.speaker_user_id else None,
                language=s.language,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                text=s.text,
                confidence=float(s.confidence) if s.confidence is not None else None,
                created_at=s.created_at,
            )
            for s in segments
        ],
    )
