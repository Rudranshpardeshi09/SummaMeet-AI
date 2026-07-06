"""RFC 7807 Problem Details error response schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """Standard error response per RFC 7807 Problem Details for HTTP APIs."""

    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type",
    )
    title: str = Field(..., description="Short human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation")
    instance: str | None = Field(
        default=None, description="URI reference of the specific occurrence"
    )
    invalid_params: list[InvalidParam] | None = Field(
        default=None,
        alias="invalid_params",
        description="List of invalid parameters for validation errors",
    )

    model_config = {"populate_by_name": True}


class InvalidParam(BaseModel):
    """Individual validation error detail."""

    name: str
    reason: str
