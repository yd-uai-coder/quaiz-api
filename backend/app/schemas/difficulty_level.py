import uuid
from datetime import datetime

from app.schemas.base import ORMReadModel


class DifficultyLevelRead(ORMReadModel):
    id: uuid.UUID
    level: int
    name: str
    description: str
    created_at: datetime
