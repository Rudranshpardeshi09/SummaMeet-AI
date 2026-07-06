from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.action_item import ActionItemResponse

class MeetingReportResponse(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    status: str
    summary: Optional[str] = None
    conclusion: Optional[str] = None
    decisions: List[str] = []
    risks: List[str] = []
    blockers: List[str] = []
    tags: List[str] = []
    model_name: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # We can embed action items directly in the report response
    action_items: List[ActionItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
