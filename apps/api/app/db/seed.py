"""Database seed script — creates initial organization, admin user, and bot API key.

Run with: python -m app.db.seed (from the apps/api directory)
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory, engine, Base
from app.models import Organization, User, ApiKey
from auth_pkg import hash_password

settings = get_settings()


def _generate_api_key() -> tuple[str, str]:
    """Generate a raw API key and its SHA-256 hash."""
    raw_key = f"nvt_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def seed_database() -> None:
    """Create initial org, admin user, and bot API key if they don't exist."""

    # Create all tables (for development — in production use Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if org already exists
        stmt = select(Organization).where(Organization.slug == settings.seed_org_slug)
        result = await session.execute(stmt)
        org = result.scalar_one_or_none()

        if org is None:
            org = Organization(
                name=settings.seed_org_name,
                slug=settings.seed_org_slug,
                status="ACTIVE",
            )
            session.add(org)
            await session.flush()
            print(f"[OK] Created organization: {org.name} ({org.slug})")
        else:
            print(f"[INFO] Organization already exists: {org.name}")

        # Check if admin user exists
        admin_stmt = select(User).where(User.email == settings.seed_admin_email)
        admin_result = await session.execute(admin_stmt)
        admin = admin_result.scalar_one_or_none()

        if admin is None:
            admin = User(
                organization_id=org.id,
                name="Admin",
                email=settings.seed_admin_email,
                password_hash=hash_password(settings.seed_admin_password),
                role="ADMIN",
                status="ACTIVE",
                password_changed_at=datetime.now(UTC),
            )
            session.add(admin)
            await session.flush()
            print(f"[OK] Created admin user: {admin.email}")
        else:
            print(f"[INFO] Admin user already exists: {admin.email}")

        # Check if bot worker API key exists
        api_key_stmt = select(ApiKey).where(ApiKey.name == "bot-worker")
        api_key_result = await session.execute(api_key_stmt)
        api_key = api_key_result.scalar_one_or_none()

        if api_key is None:
            raw_key, key_hash = _generate_api_key()
            api_key = ApiKey(
                name="bot-worker",
                key_hash=key_hash,
                is_active=True,
                created_at=datetime.now(UTC),
            )
            session.add(api_key)
            await session.flush()
            print(f"[OK] Created bot worker API key.")
            print(f"     Save this key (shown only once): {raw_key}")
        else:
            print(f"[INFO] Bot worker API key already exists.")

        await session.commit()
        print("\n[OK] Database seeding completed!")


def main() -> None:
    """Entry point for the seed script."""
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()

