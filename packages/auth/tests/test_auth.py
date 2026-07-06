"""Tests for the auth_pkg package — password hashing and JWT operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from auth_pkg.password import hash_password, verify_password


class TestPasswordHashing:
    """Test bcrypt password hashing and verification."""

    def test_hash_password_returns_bcrypt_string(self):
        hashed = hash_password("test_password_123")
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60

    def test_verify_correct_password(self):
        password = "super_secure_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt generates a random salt each time."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # Different salts
        assert verify_password("same_password", h1) is True
        assert verify_password("same_password", h2) is True

    def test_unicode_password(self):
        password = "पासवर्ड_हिंदी_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestJWTHandler:
    """Test JWT creation and verification."""

    @pytest.fixture
    def jwt_keys(self, tmp_path):
        """Generate temporary RSA keys for testing."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        priv_path = tmp_path / "test_private.pem"
        pub_path = tmp_path / "test_public.pem"
        priv_path.write_bytes(private_pem)
        pub_path.write_bytes(public_pem)

        return str(priv_path), str(pub_path)

    def test_create_and_decode_access_token(self, jwt_keys):
        from auth_pkg.jwt_handler import JWTHandler

        handler = JWTHandler(
            private_key_path=jwt_keys[0],
            public_key_path=jwt_keys[1],
            access_token_expire_minutes=15,
        )

        token = handler.create_access_token(
            user_id="usr_123",
            org_id="org_456",
            role="ADMIN",
        )

        payload = handler.decode_access_token(token)

        assert payload.user_id == "usr_123"
        assert payload.org_id == "org_456"
        assert payload.role == "ADMIN"
        assert payload.jti  # Should have a JTI

    def test_expired_token_raises(self, jwt_keys):
        from auth_pkg.jwt_handler import JWTHandler
        import jwt as pyjwt

        handler = JWTHandler(
            private_key_path=jwt_keys[0],
            public_key_path=jwt_keys[1],
            access_token_expire_minutes=-1,  # Already expired
        )

        token = handler.create_access_token(
            user_id="usr_123",
            org_id="org_456",
            role="ADMIN",
        )

        with pytest.raises(pyjwt.ExpiredSignatureError):
            handler.decode_access_token(token)

    def test_generate_refresh_token_is_uuid(self):
        from auth_pkg.jwt_handler import JWTHandler
        import uuid

        token = JWTHandler.generate_refresh_token()
        # Should be a valid UUID string
        parsed = uuid.UUID(token)
        assert str(parsed) == token
