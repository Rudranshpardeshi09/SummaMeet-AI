"""Meeting model — the central entity of the platform."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class Meeting(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "meetings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="GOOGLE_MEET"
    )
    meeting_url: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="SCHEDULED"
    )
    language_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default='["en", "hi"]'
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", back_populates="meetings")
    participants = relationship(
        "MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan", lazy="selectin"
    )
    bot_sessions = relationship("BotSession", back_populates="meeting", lazy="selectin")
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="meeting", lazy="noload"
    )
    report = relationship(
        "MeetingReport", back_populates="meeting", uselist=False, lazy="selectin"
    )
    audio_chunks = relationship(
        "AudioChunk", back_populates="meeting", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('SCHEDULED', 'BOT_STARTING', 'WAITING_FOR_ADMISSION', "
            "'IN_PROGRESS', 'PROCESSING_TRANSCRIPT', 'GENERATING_REPORT', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="chk_meeting_status",
        ),
        Index(
            "idx_meetings_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
        Index(
            "idx_meetings_org_time",
            "organization_id",
            "scheduled_start_time",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_meetings_project_time",
            "project_id",
            "scheduled_start_time",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<Meeting {self.title} ({self.status})>"

    @property
    def host_id(self) -> uuid.UUID:
        return self.host_user_id

    @property
    def description(self) -> str | None:
        return self.notes

    @property
    def scheduled_at(self) -> datetime:
        return self.scheduled_start_time

    @property
    def started_at(self) -> datetime | None:
        return self.actual_start_time

    @property
    def ended_at(self) -> datetime | None:
        return self.actual_end_time
