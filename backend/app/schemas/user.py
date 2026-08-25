import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole
from app.schemas.base import ORMReadModel


class UserBase(BaseModel):
    display_name: str


class UserCreate(UserBase):
    password: str


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: UserRole | None = None
    password: str | None = None
    current_password: str | None = None


class UserRead(UserBase, ORMReadModel):
    id: uuid.UUID
    is_active: bool
    role: UserRole
    created_at: datetime


class UserSummary(BaseModel):
    challenged_count: int
    corrected_count: int


class UserBulkDeleteRequest(BaseModel):
    user_ids: list[uuid.UUID]
