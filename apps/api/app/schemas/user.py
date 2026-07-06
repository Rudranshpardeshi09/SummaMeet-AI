import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    status: str | None = None
    preferred_language: str | None = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    status: str
    preferred_language: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
