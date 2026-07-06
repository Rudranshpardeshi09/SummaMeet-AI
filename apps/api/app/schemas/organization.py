import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: str | None = None

class OrganizationResponse(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime
