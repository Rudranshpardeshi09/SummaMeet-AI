"""Organization model — tenant boundary for multi-tenancy."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="ACTIVE"
    )

    # Relationships
    users = relationship("User", back_populates="organization", lazy="selectin")
    projects = relationship("Project", back_populates="organization", lazy="selectin")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="chk_org_status"),
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"
