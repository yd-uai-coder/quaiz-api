from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category
from app.repositories.category import CategoryRepository


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = CategoryRepository(session)

    async def list_categories(self) -> list[Category]:
        """カテゴリ一覧を返す(クイズ生成・絞り込みのドロップダウン用)。"""
        return await self._repo.list_all()
