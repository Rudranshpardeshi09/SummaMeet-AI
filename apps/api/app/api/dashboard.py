from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.meeting import Meeting
from app.models.action_item import ActionItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/overview")
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate statistics for the dashboard."""
    # 1. Total meetings
    meetings_stmt = select(func.count(Meeting.id)).where(
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    total_meetings = await db.scalar(meetings_stmt)

    # 2. Action Items (total and completed)
    # Join with Meeting to filter by organization
    base_action_items_stmt = select(func.count(ActionItem.id)).join(
        Meeting, ActionItem.meeting_id == Meeting.id
    ).where(
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    
    total_action_items = await db.scalar(base_action_items_stmt)
    
    completed_action_items_stmt = base_action_items_stmt.where(
        ActionItem.status == 'COMPLETED'
    )
    completed_action_items = await db.scalar(completed_action_items_stmt)
    
    completion_rate = 0.0
    if total_action_items and total_action_items > 0:
        completion_rate = round((completed_action_items / total_action_items) * 100, 1)

    return {
        "total_meetings": total_meetings or 0,
        "total_action_items": total_action_items or 0,
        "completed_action_items": completed_action_items or 0,
        "completion_rate_percent": completion_rate
    }
