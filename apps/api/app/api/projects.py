import uuid
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.pagination import PaginatedResponse
from app.core.pagination import encode_cursor, decode_cursor
from app.core.errors import NotFoundError, ForbiddenError
from app.core.audit import log_audit_event

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects in the organization with cursor pagination."""
    stmt = select(Project).where(
        Project.organization_id == current_user.organization_id,
        Project.deleted_at.is_(None)
    )

    if cursor:
        decoded_cursor = decode_cursor(cursor, is_datetime=True)
        if decoded_cursor:
            stmt = stmt.where(Project.created_at < decoded_cursor)

    stmt = stmt.order_by(desc(Project.created_at)).limit(limit + 1)
    
    result = await db.execute(stmt)
    projects = result.scalars().all()

    has_more = len(projects) > limit
    if has_more:
        projects = projects[:limit]

    next_cursor = encode_cursor(projects[-1].created_at) if projects else None

    return PaginatedResponse(
        data=projects,
        next_cursor=next_cursor,
        has_more=has_more
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific project by ID."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id,
        Project.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError(detail="Project not found")

    return project

@router.post("", response_model=ProjectResponse)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    new_project = Project(
        organization_id=current_user.organization_id,
        name=project_in.name,
        description=project_in.description,
        created_by=current_user.id,
    )
    db.add(new_project)
    await db.flush()

    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="CREATE",
        entity_type="Project",
        entity_id=new_project.id,
        changes={"name": new_project.name}
    )
    
    await db.commit()
    await db.refresh(new_project)

    return new_project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id,
        Project.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError(detail="Project not found")

    changes = {}
    for field, value in project_in.model_dump(exclude_unset=True).items():
        old_val = getattr(project, field)
        if old_val != value:
            changes[field] = {"old": old_val, "new": value}
            setattr(project, field, value)

    if changes:
        await log_audit_event(
            session=db,
            actor_id=current_user.id,
            organization_id=current_user.organization_id,
            action="UPDATE",
            entity_type="Project",
            entity_id=project.id,
            changes=changes
        )
        await db.commit()
        await db.refresh(project)

    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a project."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id,
        Project.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError(detail="Project not found")

    project.deleted_at = datetime.now(UTC)
    
    await log_audit_event(
        session=db,
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        action="DELETE",
        entity_type="Project",
        entity_id=project.id
    )
    
    await db.commit()
    return {"message": "Project deleted successfully"}
