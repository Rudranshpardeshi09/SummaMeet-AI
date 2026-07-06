"""ActionItem model — extracted tasks from meeting reports."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin


class ActionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "action_items"

    meeting_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="NOT_STARTED"
    )
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    report = relationship("MeetingReport", back_populates="action_items")

    __table_args__ = (
        CheckConstraint(
            "status IN ('NOT_STARTED', 'PARTIALLY_DONE', 'DONE', 'BLOCKED')",
            name="chk_action_status",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_action_priority",
        ),
        Index("idx_action_items_meeting", "meeting_id"),
        Index("idx_action_items_owner", "owner_user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<ActionItem {self.title[:30]} ({self.status})>"
