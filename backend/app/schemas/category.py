import uuid
from datetime import datetime

from app.schemas.base import ORMReadModel


class CategoryRead(ORMReadModel):
    id: uuid.UUID
    name: str
    created_at: datetime
