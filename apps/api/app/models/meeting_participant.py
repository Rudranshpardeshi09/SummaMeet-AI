"""MeetingParticipant model — links users to meetings."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin


class MeetingParticipant(Base, UUIDMixin):
    __tablename__ = "meeting_participants"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="USER"
    )
    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="INVITED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_user"),
        CheckConstraint(
            "participant_type IN ('HOST', 'USER')", name="chk_participant_type"
        ),
        CheckConstraint(
            "attendance_status IN ('INVITED', 'JOINED', 'ABSENT')",
            name="chk_attendance",
        ),
    )

    def __repr__(self) -> str:
        return f"<MeetingParticipant meeting={self.meeting_id} user={self.user_id}>"
