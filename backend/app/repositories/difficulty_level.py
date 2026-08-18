from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import DifficultyLevel
from app.repositories.base import CRUDRepository


class DifficultyLevelRepository(CRUDRepository[DifficultyLevel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DifficultyLevel)

    async def list_all(self) -> list[DifficultyLevel]:
        """難易度をlevel順(1〜5)で全件取得する。"""
        return await super().list_all(order_by=DifficultyLevel.level)
