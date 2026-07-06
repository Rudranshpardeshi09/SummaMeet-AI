from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.schemas.organization import OrganizationResponse, OrganizationUpdate
from app.core.errors import NotFoundError, ForbiddenError
from app.core.audit import log_audit_event

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the organization for the current user."""
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()
    
    if not org:
        raise NotFoundError(detail="Organization not found")
        
    return org

@router.patch("/me", response_model=OrganizationResponse)
async def update_my_organization(
    org_update: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the organization details (Admin only)."""
    if current_user.role != "admin":
        raise ForbiddenError(detail="Only organization admins can update organization details")
        
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()
    
    if not org:
        raise NotFoundError(detail="Organization not found")
        
    changes = {}
    if org_update.name is not None and org_update.name != org.name:
        changes["name"] = {"old": org.name, "new": org_update.name}
        org.name = org_update.name
        
    if changes:
        await log_audit_event(
            session=db,
            actor_id=current_user.id,
            organization_id=org.id,
            action="UPDATE",
            entity_type="Organization",
            entity_id=org.id,
            changes=changes
        )
        await db.commit()
        await db.refresh(org)
        
    return org
