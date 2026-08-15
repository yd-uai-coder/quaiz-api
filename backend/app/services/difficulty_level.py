from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import DifficultyLevel
from app.repositories.difficulty_level import DifficultyLevelRepository


class DifficultyLevelService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = DifficultyLevelRepository(session)

    async def list_difficulty_levels(self) -> list[DifficultyLevel]:
        """難易度一覧を返す(クイズ生成のドロップダウン用)。"""
        return await self._repo.list_all()
