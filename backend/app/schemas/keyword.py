import uuid
from datetime import datetime

from app.schemas.base import ORMReadModel


class KeywordRead(ORMReadModel):
    id: uuid.UUID
    keyword: str
    created_at: datetime
