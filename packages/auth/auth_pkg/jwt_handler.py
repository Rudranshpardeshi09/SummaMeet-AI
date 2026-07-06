"""JWT creation and verification using RS256 asymmetric signing.

Access tokens are short-lived (15 min) and contain user claims.
Refresh tokens are opaque UUIDs stored in the database (not JWTs).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT access token claims."""

    user_id: str
    org_id: str
    role: str
    jti: str  # JWT ID for blacklisting
    exp: datetime
    iat: datetime


class JWTHandler:
    """Handles JWT access token creation and verification using RS256."""

    def __init__(
        self,
        private_key_path: str | Path,
        public_key_path: str | Path,
        access_token_expire_minutes: int = 15,
        algorithm: str = "RS256",
    ) -> None:
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes

        private_path = Path(private_key_path)
        public_path = Path(public_key_path)

        if private_path.exists():
            self._private_key = private_path.read_text()
        else:
            self._private_key = ""

        if public_path.exists():
            self._public_key = public_path.read_text()
        else:
            self._public_key = ""

    def create_access_token(
        self,
        user_id: str,
        org_id: str,
        role: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a signed JWT access token.

        Args:
            user_id: The user's UUID.
            org_id: The user's organization UUID.
            role: The user's role (ADMIN, HOST, USER).
            extra_claims: Optional additional claims to include.

        Returns:
            The encoded JWT string.
        """
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self._access_token_expire_minutes)
        jti = str(uuid.uuid4())

        payload: dict[str, Any] = {
            "sub": user_id,
            "org_id": org_id,
            "role": role,
            "jti": jti,
            "iat": now,
            "exp": expire,
            "type": "access",
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self._private_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> TokenPayload:
        """Decode and verify a JWT access token.

        Args:
            token: The encoded JWT string.

        Returns:
            TokenPayload with decoded claims.

        Raises:
            jwt.ExpiredSignatureError: If the token has expired.
            jwt.InvalidTokenError: If the token is invalid.
        """
        decoded = jwt.decode(
            token,
            self._public_key,
            algorithms=[self._algorithm],
            options={"require": ["sub", "org_id", "role", "jti", "exp", "iat"]},
        )

        return TokenPayload(
            user_id=decoded["sub"],
            org_id=decoded["org_id"],
            role=decoded["role"],
            jti=decoded["jti"],
            exp=datetime.fromtimestamp(decoded["exp"], tz=UTC),
            iat=datetime.fromtimestamp(decoded["iat"], tz=UTC),
        )

    @staticmethod
    def generate_refresh_token() -> str:
        """Generate an opaque refresh token (UUID v4).

        Refresh tokens are NOT JWTs — they are random UUIDs stored
        in the database's refresh_tokens table.
        """
        return str(uuid.uuid4())
