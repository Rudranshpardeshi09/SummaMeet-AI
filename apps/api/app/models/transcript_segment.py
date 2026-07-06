"""TranscriptSegment model — individual speech-to-text fragments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin


class TranscriptSegment(Base, UUIDMixin):
    __tablename__ = "transcript_segments"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bot_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_label: Mapped[str] = mapped_column(String(80), nullable=False)
    speaker_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="en"
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa_text("NOW()"),
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="transcript_segments")
    bot_session = relationship("BotSession", back_populates="transcript_segments")

    __table_args__ = (
        Index("idx_transcript_sequence", "meeting_id", "sequence_no"),
        Index("idx_transcript_time", "meeting_id", "start_ms"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptSegment seq={self.sequence_no} speaker={self.speaker_label}>"
