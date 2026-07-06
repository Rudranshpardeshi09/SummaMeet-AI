"""Project model — groups meetings under organizational folders."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class Project(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", back_populates="projects")
    meetings = relationship("Meeting", back_populates="project", lazy="selectin")

    __table_args__ = (
        Index(
            "idx_projects_org_name",
            "organization_id",
            "name",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
