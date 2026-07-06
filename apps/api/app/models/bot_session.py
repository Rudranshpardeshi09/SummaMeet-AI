"""BotSession model — tracks bot browser process lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin


class BotSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "bot_sessions"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="QUEUED"
    )
    worker_node: Mapped[str | None] = mapped_column(String(120), nullable=True)
    join_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_event_log: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default="[]"
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="bot_sessions")
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="bot_session", lazy="noload"
    )
    audio_chunks = relationship(
        "AudioChunk", back_populates="bot_session", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED', 'JOINING', 'WAITING_FOR_ADMISSION', "
            "'JOINED', 'RECORDING', 'ENDED', 'FAILED')",
            name="chk_bot_session_status",
        ),
        Index("idx_bot_sessions_meeting", "meeting_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BotSession meeting={self.meeting_id} status={self.status}>"
