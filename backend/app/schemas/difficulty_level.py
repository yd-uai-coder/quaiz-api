from datetime import datetime

from app.schemas.base import ORMReadModel


class DifficultyLevelRead(ORMReadModel):
    id: int
    name: str
    description: str
    created_at: datetime
