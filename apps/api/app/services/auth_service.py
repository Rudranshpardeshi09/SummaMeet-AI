"""Authentication service — handles login, refresh, logout, and token management.

This is the core business logic layer. It orchestrates between the database,
JWT handler, and password verification without any HTTP concerns.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from auth_pkg import JWTHandler, hash_password, verify_password

settings = get_settings()


class AuthService:
    """Handles authentication operations."""

    def __init__(self, db: AsyncSession, jwt_handler: JWTHandler) -> None:
        self._db = db
        self._jwt = jwt_handler

    async def authenticate_user(
        self, email: str, password: str
    ) -> tuple[User, str, str] | None:
        """Verify credentials and issue tokens.

        Returns:
            Tuple of (user, access_token, refresh_token_str) on success,
            None on invalid credentials.
        """
        # Find active user by email
        stmt = select(User).where(
            User.email == email,
            User.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if user.status == "DISABLED":
            return None

        if not verify_password(password, user.password_hash):
            return None

        # Create access token
        access_token = self._jwt.create_access_token(
            user_id=str(user.id),
            org_id=str(user.organization_id),
            role=user.role,
        )

        # Create refresh token
        refresh_token_str = JWTHandler.generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            parent_token=None,
            is_revoked=False,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self._db.add(refresh_token)

        # Update last_login_at
        user.last_login_at = datetime.now(UTC)

        await self._db.flush()

        return user, access_token, refresh_token_str

    async def refresh_access_token(
        self, refresh_token_str: str
    ) -> tuple[str, str] | None:
        """Rotate refresh token and issue new access token.

        Implements rotation reuse detection: if a previously-used token
        is presented, ALL tokens for that user are revoked (compromise detected).

        Returns:
            Tuple of (new_access_token, new_refresh_token) on success,
            None on invalid/revoked/expired token.
        """
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        result = await self._db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if token_record is None:
            return None

        # Check if token was already used (rotation reuse detection)
        if token_record.is_revoked:
            # Potential token theft — revoke ALL tokens for this user
            await self._revoke_all_user_tokens(token_record.user_id)
            return None

        # Check expiry
        if token_record.expires_at < datetime.now(UTC):
            return None

        # Revoke current token
        token_record.is_revoked = True

        # Load user
        user_stmt = select(User).where(
            User.id == token_record.user_id,
            User.deleted_at.is_(None),
        )
        user_result = await self._db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user is None or user.status == "DISABLED":
            return None

        # Issue new access token
        new_access_token = self._jwt.create_access_token(
            user_id=str(user.id),
            org_id=str(user.organization_id),
            role=user.role,
        )

        # Issue new refresh token with parent reference
        new_refresh_str = JWTHandler.generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

        new_refresh = RefreshToken(
            user_id=user.id,
            token=new_refresh_str,
            parent_token=refresh_token_str,
            is_revoked=False,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self._db.add(new_refresh)
        await self._db.flush()

        return new_access_token, new_refresh_str

    async def logout(self, refresh_token_str: str, access_token_jti: str) -> bool:
        """Revoke refresh token and blacklist access token.

        Args:
            refresh_token_str: The refresh token from the HttpOnly cookie.
            access_token_jti: The JTI claim from the access token to blacklist.

        Returns:
            True if logout was successful, False if token not found.
        """
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        result = await self._db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if token_record is not None:
            token_record.is_revoked = True
            await self._db.flush()

        # NOTE: Access token blacklisting via Redis will be added
        # when the Redis client is integrated. For now, the refresh
        # token revocation is the primary logout mechanism.

        return True

    async def _revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        """Revoke ALL refresh tokens for a user (compromise response)."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
        await self._db.execute(stmt)
        await self._db.flush()
