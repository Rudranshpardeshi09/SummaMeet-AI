"""ReportArtifact model — PDF/JSON files stored in MinIO."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin


class ReportArtifact(Base, UUIDMixin):
    __tablename__ = "report_artifacts"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    report = relationship("MeetingReport", back_populates="artifacts")

    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('PDF', 'JSON_EXPORT')",
            name="chk_artifact_type",
        ),
        Index("idx_artifacts_lookup", "meeting_id", "artifact_type"),
    )

    def __repr__(self) -> str:
        return f"<ReportArtifact {self.file_name} ({self.artifact_type})>"
