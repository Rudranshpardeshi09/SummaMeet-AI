"""Pydantic schemas for transcript API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSegmentCreate(BaseModel):
    """A single transcript segment to be created."""

    sequence_no: int
    speaker_label: str
    speaker_user_id: str | None = None
    language: str = "en"
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


class BatchCreateSegmentsRequest(BaseModel):
    """POST /internal/transcripts/segments/batch — batch create segments."""

    meeting_id: str
    bot_session_id: str
    segments: list[TranscriptSegmentCreate] = Field(
        ..., min_length=1, max_length=200
    )


class TranscriptSegmentResponse(BaseModel):
    """Response for a single transcript segment."""

    id: str
    meeting_id: str
    bot_session_id: str
    sequence_no: int
    speaker_label: str
    speaker_user_id: str | None
    language: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    """GET /meetings/{id}/transcript — full transcript response."""

    meeting_id: str
    total_segments: int
    total_duration_ms: int
    speakers: list[str]
    languages: list[str]
    segments: list[TranscriptSegmentResponse]


class AudioChunkInfo(BaseModel):
    """Audio chunk metadata returned from the API."""

    chunk_index: int
    minio_key: str
    duration_ms: int
    size_bytes: int
    format: str
