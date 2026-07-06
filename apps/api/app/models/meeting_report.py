"""MeetingReport model — structured AI-generated meeting reports."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin


class MeetingReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meeting_reports"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="NOT_STARTED"
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    risks: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    blockers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="report")
    action_items = relationship(
        "ActionItem", back_populates="report", cascade="all, delete-orphan"
    )
    artifacts = relationship(
        "ReportArtifact", back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="chk_report_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<MeetingReport meeting={self.meeting_id} status={self.status}>"
