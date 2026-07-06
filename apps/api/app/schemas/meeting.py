"""Pydantic schemas for meeting API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class UpdateMeetingStatusRequest(BaseModel):
    """PATCH /internal/meetings/{id}/status — update meeting status."""

    status: str = Field(
        ...,
        description=(
            "One of: SCHEDULED, BOT_STARTING, WAITING_FOR_ADMISSION, "
            "IN_PROGRESS, PROCESSING_TRANSCRIPT, GENERATING_REPORT, "
            "COMPLETED, FAILED, CANCELLED"
        ),
    )
    failure_reason: str | None = None


class MeetingParticipantBase(BaseModel):
    user_id: uuid.UUID
    role: str = "viewer"


class MeetingCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    meeting_url: str
    scheduled_at: datetime | None = None
    participants: list[MeetingParticipantBase] | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    meeting_url: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = None


class MeetingParticipantResponse(MeetingParticipantBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    meeting_id: uuid.UUID


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    host_id: uuid.UUID | None
    title: str
    description: str | None
    meeting_url: str
    status: str
    platform: str | None = None
    scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
    participants: list[MeetingParticipantResponse] = []

    def model_post_init(self, __context: object) -> None:
        """Derive platform from meeting_url after initialization."""
        if self.meeting_url and self.platform is None:
            url_lower = self.meeting_url.lower()
            if "meet.google.com" in url_lower:
                self.platform = "google_meet"
            elif "jitsi" in url_lower or "meet.jit.si" in url_lower or "8x8.vc" in url_lower:
                self.platform = "jitsi"
            else:
                self.platform = "unknown"
