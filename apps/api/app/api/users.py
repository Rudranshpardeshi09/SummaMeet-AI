import secrets
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.pagination import PaginatedResponse
from app.core.pagination import encode_cursor, decode_cursor
from app.core.errors import NotFoundError, ForbiddenError, ConflictError
from app.core.audit import log_audit_event

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List users in the organization with cursor pagination."""
    stmt = select(User).where(
        User.organization_id == current_user.organization_id,
        User.deleted_at.is_(None)
    )

    if cursor:
        decoded_cursor = decode_cursor(cursor, is_datetime=True)
        if decoded_cursor:
            stmt = stmt.where(User.created_at < decoded_cursor)

    stmt = stmt.order_by(desc(User.created_at)).limit(limit + 1)
    
    result = await db.execute(stmt)
    users = result.scalars().all()

    has_more = len(users) > limit
    if has_more:
        users = users[:limit]

    next_cursor = encode_cursor(users[-1].created_at) if users else None

    return PaginatedResponse(
        data=users,
        next_cursor=next_cursor,
        has_more=has_more
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the currently logged-in user's profile."""
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user by ID."""
    stmt = select(User).where(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
        User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(detail="User not found")

    return user

@router.post("", response_model=dict[str, Any])
async def invite_user(
    user_in: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user to the organization (Admin only)."""
    if current_user.role != "admin":
        raise ForbiddenError(detail="Only admins can invite users")

    # Check if email exists
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ConflictError(detail="User with this email already exists")

    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=7)

    new_user = User(
        organization_id=current_user.organization_id,
        email=user_in.email,
        name=user_in.name,
        role=user_in.role,
        status="PENDING",
        invite_token=invite_token,
        invite_expires_at=expires_at,
    )
    db.add(new_user)
    await db.flush()

    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="CREATE",
        entity_type="User",
        entity_id=new_user.id,
        changes={"email": new_user.email, "role": new_user.role}
    )
    
    await db.commit()
    await db.refresh(new_user)

    return {
        "user": UserResponse.model_validate(new_user),
        "invite_token": invite_token,
        "invite_url": f"http://localhost:3000/invite?token={invite_token}"
    }

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a user (Admin only)."""
    if current_user.role != "admin":
        raise ForbiddenError(detail="Only admins can update users")

    stmt = select(User).where(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
        User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(detail="User not found")

    changes = {}
    for field, value in user_in.model_dump(exclude_unset=True).items():
        old_val = getattr(user, field)
        if old_val != value:
            changes[field] = {"old": old_val, "new": value}
            setattr(user, field, value)

    if changes:
        await log_audit_event(
            session=db,
            actor_id=current_user.id,
            organization_id=current_user.organization_id,
            action="UPDATE",
            entity_type="User",
            entity_id=user.id,
            changes=changes
        )
        await db.commit()
        await db.refresh(user)

    return user

@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a user (Admin only)."""
    if current_user.role != "admin":
        raise ForbiddenError(detail="Only admins can delete users")

    if user_id == current_user.id:
        raise ConflictError(detail="Cannot delete yourself")

    stmt = select(User).where(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
        User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(detail="User not found")

    user.deleted_at = datetime.now(UTC)
    
    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="DELETE",
        entity_type="User",
        entity_id=user.id
    )
    
    await db.commit()
    return {"message": "User deleted successfully"}
