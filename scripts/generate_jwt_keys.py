"""Generate RSA key pair for JWT RS256 signing.

Creates jwt_keys/ directory with:
  - jwt_private.pem (RSA 2048-bit private key)
  - jwt_public.pem  (corresponding public key)

Usage:
  python scripts/generate_jwt_keys.py
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keys(output_dir: str = "jwt_keys") -> None:
    """Generate RSA-2048 key pair for JWT signing."""
    key_dir = Path(output_dir)
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = key_dir / "jwt_private.pem"
    public_key_path = key_dir / "jwt_public.pem"

    if private_key_path.exists():
        print(f"⚠ Private key already exists at {private_key_path}")
        print("  Delete it first if you want to regenerate.")
        return

    # Generate RSA-2048 private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serialize private key (unencrypted — use encrypted in production)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)

    # Restrict permissions on private key
    try:
        os.chmod(private_key_path, 0o600)
    except OSError:
        pass  # Windows doesn't support chmod the same way

    print(f"✓ Private key: {private_key_path}")
    print(f"✓ Public key:  {public_key_path}")
    print("\nKeys generated successfully! Add jwt_keys/ to .gitignore (already done).")


if __name__ == "__main__":
    generate_keys()
