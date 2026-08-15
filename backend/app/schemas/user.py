import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole
from app.schemas.base import ORMReadModel


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = None


class UserRead(UserBase, ORMReadModel):
    id: uuid.UUID
    is_active: bool
    role: UserRole
    created_at: datetime


class UserSummary(BaseModel):
    challenged_count: int
    corrected_count: int
