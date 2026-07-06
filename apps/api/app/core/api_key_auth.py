"""API key authentication dependency for service-to-service (bot/worker → API) calls.

Usage in route handlers:
    @router.post("/internal/endpoint")
    async def internal_endpoint(api_key: ValidApiKey):
        ...
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.api_key import ApiKey

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_api_key(raw_key: str) -> str:
    """Hash an API key with SHA-256 for storage/lookup comparison."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_valid_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKey:
    """Validate the X-API-Key header against the database.

    Raises 401 if missing, 403 if invalid or inactive.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = _hash_api_key(api_key)
    stmt = select(ApiKey).where(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active.is_(True),
    )
    result = await db.execute(stmt)
    key_record = result.scalar_one_or_none()

    if key_record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or inactive API key",
        )

    return key_record


# Type alias for route dependencies
ValidApiKey = Annotated[ApiKey, Depends(get_valid_api_key)]
