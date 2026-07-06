"""Authentication API routes — login, refresh, logout.

All responses follow the contracts defined in the HLD & API Design document.
Refresh tokens are set as HttpOnly Secure cookies — never exposed in response body.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import CurrentToken, get_jwt_handler
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    UserBrief,
)
from app.services.auth_service import AuthService
from auth_pkg import JWTHandler

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token as an HttpOnly Secure cookie."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
):
    """Authenticate user and issue JWT access token + refresh token cookie.

    The refresh token is set as an HttpOnly Secure cookie and is NOT
    included in the JSON response body for security.
    """
    auth_service = AuthService(db, jwt_handler)
    result = await auth_service.authenticate_user(body.email, body.password)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user, access_token, refresh_token_str = result

    # Set refresh token as HttpOnly cookie
    _set_refresh_cookie(response, refresh_token_str)

    return LoginResponse(
        accessToken=access_token,
        tokenType="Bearer",
        expiresIn=settings.jwt_access_token_expire_minutes * 60,
        user=UserBrief(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=user.role,
        ),
    )


@router.post(
    "/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK
)
async def refresh_token(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    """Rotate refresh token and issue new access token.

    Uses the HttpOnly refresh_token cookie. If the token has already been
    used (rotation reuse detection), ALL tokens for that user are revoked
    as a security measure against token theft.
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    auth_service = AuthService(db, jwt_handler)
    result = await auth_service.refresh_access_token(refresh_token)

    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_access_token, new_refresh_token = result

    # Set rotated refresh token
    _set_refresh_cookie(response, new_refresh_token)

    return RefreshResponse(
        accessToken=new_access_token,
        tokenType="Bearer",
        expiresIn=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    token: CurrentToken,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    """Revoke refresh token and blacklist access token.

    Requires a valid access token in the Authorization header.
    Clears the refresh token cookie.
    """
    auth_service = AuthService(db, jwt_handler)

    if refresh_token:
        await auth_service.logout(refresh_token, token.jti)

    _clear_refresh_cookie(response)

    return LogoutResponse()
