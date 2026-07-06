"""Pydantic schemas for bot session API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateBotSessionRequest(BaseModel):
    """POST /internal/bot/sessions — create a new bot session."""

    meeting_id: str
    worker_node: str | None = None


class UpdateBotStatusRequest(BaseModel):
    """PATCH /internal/bot/sessions/{id}/status — update bot session status."""

    status: str = Field(
        ...,
        description="One of: QUEUED, JOINING, WAITING_FOR_ADMISSION, JOINED, RECORDING, ENDED, FAILED",
    )
    failure_reason: str | None = None


class BotEventRequest(BaseModel):
    """POST /internal/bot/sessions/{id}/events — append an event to the log."""

    event_type: str
    details: dict | None = None
    timestamp: datetime | None = None


class RegisterAudioChunkRequest(BaseModel):
    """POST /internal/bot/sessions/{id}/audio-chunks — register an uploaded chunk."""

    chunk_index: int
    minio_key: str
    duration_ms: int
    size_bytes: int
    format: str = "webm"


class AudioChunkResponse(BaseModel):
    """Response for a single audio chunk."""

    id: str
    bot_session_id: str
    meeting_id: str
    chunk_index: int
    minio_key: str
    duration_ms: int
    size_bytes: int
    format: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BotSessionResponse(BaseModel):
    """Response for a bot session."""

    id: str
    meeting_id: str
    status: str
    worker_node: str | None
    join_attempted_at: datetime | None
    joined_at: datetime | None
    ended_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
