import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.action_item import ActionItem
from app.models.meeting import Meeting
from app.schemas.action_item import ActionItemResponse, ActionItemUpdate
from app.schemas.pagination import PaginatedResponse
from app.core.errors import NotFoundError

router = APIRouter(tags=["Action Items"])

@router.get("/action-items", response_model=PaginatedResponse[ActionItemResponse])
async def list_action_items(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List action items across all meetings in the user's organization."""
    offset = 0
    if cursor:
        try:
            offset = int(cursor)
        except ValueError:
            pass

    stmt = select(ActionItem).join(Meeting, ActionItem.meeting_id == Meeting.id).where(
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )

    if status:
        stmt = stmt.where(ActionItem.status == status)
    if priority:
        stmt = stmt.where(ActionItem.priority == priority)
    if owner_id:
        stmt = stmt.where(ActionItem.owner_user_id == owner_id)

    stmt = stmt.order_by(ActionItem.created_at.desc()).offset(offset).limit(limit + 1)
    
    result = await db.execute(stmt)
    items = result.scalars().all()

    has_next = len(items) > limit
    items_to_return = items[:limit]
    next_cursor = str(offset + limit) if has_next else None

    return {
        "data": items_to_return,
        "next_cursor": next_cursor,
        "has_more": has_next
    }

@router.patch("/action-items/{item_id}", response_model=ActionItemResponse)
async def update_action_item(
    item_id: uuid.UUID,
    body: ActionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update status, priority, or assignee of an action item."""
    stmt = select(ActionItem).join(Meeting, ActionItem.meeting_id == Meeting.id).where(
        ActionItem.id == item_id,
        Meeting.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise NotFoundError(detail="Action item not found")

    if body.status is not None:
        item.status = body.status
    if body.priority is not None:
        item.priority = body.priority
    if body.due_date is not None:
        item.due_date = body.due_date
    if body.owner_user_id is not None:
        item.owner_user_id = body.owner_user_id

    await db.commit()
    await db.refresh(item)
    return item
