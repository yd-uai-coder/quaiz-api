import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import ORMReadModel


class CategoryRead(ORMReadModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class CategoryRanking(BaseModel):
    id: uuid.UUID
    name: str
    quiz_count: int
