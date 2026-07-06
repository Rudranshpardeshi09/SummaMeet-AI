from typing import Optional
import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class ActionItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    status: str = "NOT_STARTED"

class ActionItemUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    owner_user_id: Optional[uuid.UUID] = None

class ActionItemResponse(ActionItemBase):
    id: uuid.UUID
    meeting_id: uuid.UUID
    meeting_report_id: uuid.UUID
    owner_user_id: Optional[uuid.UUID] = None
    source_excerpt: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
