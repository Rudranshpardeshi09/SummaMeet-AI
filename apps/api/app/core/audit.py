import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog

async def log_audit_event(
    session: AsyncSession,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any] | None = None,
) -> None:
    """Create an audit log entry for a mutation."""
    audit_log = AuditLog(
        actor_user_id=actor_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=changes or {},
    )
    session.add(audit_log)
    # Note: we don't commit here, the caller should commit the transaction
