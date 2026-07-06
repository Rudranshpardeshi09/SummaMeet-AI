"""AudioChunk model — tracks uploaded audio chunks from bot recording sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin


class AudioChunk(Base, UUIDMixin):
    __tablename__ = "audio_chunks"

    bot_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bot_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    minio_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="webm"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa_text("NOW()"),
    )

    # Relationships
    bot_session = relationship("BotSession", back_populates="audio_chunks")
    meeting = relationship("Meeting", back_populates="audio_chunks")

    __table_args__ = (
        Index(
            "idx_audio_chunks_session_order",
            "bot_session_id",
            "chunk_index",
            unique=True,
        ),
        Index("idx_audio_chunks_meeting", "meeting_id"),
    )

    def __repr__(self) -> str:
        return f"<AudioChunk session={self.bot_session_id} index={self.chunk_index}>"
