"""User model — system users with roles (ADMIN, HOST, USER)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="INVITED"
    )
    preferred_language: Mapped[str | None] = mapped_column(
        String(10), default="en"
    )
    invite_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organization = relationship("Organization", back_populates="users")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'HOST', 'USER')", name="chk_user_role"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INVITED', 'DISABLED')", name="chk_user_status"
        ),
        Index(
            "idx_users_org_role",
            "organization_id",
            "role",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_users_email",
            "email",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
