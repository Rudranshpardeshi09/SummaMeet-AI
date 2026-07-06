"""Security dependencies for FastAPI — JWT verification, RBAC guards, and current user injection.

Usage in route handlers:
    @router.get("/admin-only")
    async def admin_endpoint(user: CurrentUser = Depends(require_role("ADMIN"))):
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from auth_pkg import JWTHandler
from auth_pkg.jwt_handler import TokenPayload

import jwt as pyjwt

settings = get_settings()

# Reusable JWT handler instance
_jwt_handler = JWTHandler(
    private_key_path=settings.jwt_private_key_path,
    public_key_path=settings.jwt_public_key_path,
    access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    algorithm=settings.jwt_algorithm,
)

# FastAPI security scheme
_bearer_scheme = HTTPBearer(auto_error=False)


def get_jwt_handler() -> JWTHandler:
    """FastAPI dependency returning the JWT handler singleton."""
    return _jwt_handler


async def get_current_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> TokenPayload:
    """Extract and verify JWT from Authorization header.

    Raises 401 if missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _jwt_handler.decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user(
    token: Annotated[TokenPayload, Depends(get_current_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Load the full User object from the database using JWT claims.

    Raises 401 if user not found or disabled.
    """
    stmt = select(User).where(
        User.id == token.user_id,
        User.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or user.status == "DISABLED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
        )

    return user


# Type alias for use in route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentToken = Annotated[TokenPayload, Depends(get_current_token)]


def require_role(*allowed_roles: str):
    """Create a dependency that enforces role-based access.

    Usage:
        @router.get("/admin-only")
        async def admin_view(user = Depends(require_role("ADMIN"))):
            ...

        @router.get("/host-or-admin")
        async def mixed_view(user = Depends(require_role("ADMIN", "HOST"))):
            ...
    """

    async def _role_checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return user

    return _role_checker
