"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserBrief(BaseModel):
    """Minimal user info returned in auth responses."""

    id: str
    name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    """POST /auth/login response body."""

    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")
    user: UserBrief

    model_config = {"populate_by_name": True}


class RefreshResponse(BaseModel):
    """POST /auth/refresh response body."""

    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")

    model_config = {"populate_by_name": True}


class LogoutResponse(BaseModel):
    """POST /auth/logout response body."""

    message: str = "Successfully logged out"
