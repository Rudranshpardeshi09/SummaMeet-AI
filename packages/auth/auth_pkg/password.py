"""Password hashing and verification using bcrypt.

Uses work factor 12 as specified in the security architecture.
"""

from __future__ import annotations

import bcrypt

_BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with work factor 12.

    Returns the full bcrypt hash string (includes salt and algorithm info).
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Returns True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )
