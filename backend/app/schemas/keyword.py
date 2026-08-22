import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import ORMReadModel


class KeywordRead(ORMReadModel):
    id: uuid.UUID
    keyword: str
    created_at: datetime


class KeywordRanking(BaseModel):
    id: uuid.UUID
    keyword: str
    quiz_count: int
