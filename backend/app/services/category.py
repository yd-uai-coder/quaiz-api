from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryRanking


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = CategoryRepository(session)

    async def list_categories(self) -> list[Category]:
        """カテゴリ一覧を返す(クイズ生成・絞り込みのドロップダウン用)。"""
        return await self._repo.list_all()

    async def list_ranking(self, *, limit: int | None = None) -> list[CategoryRanking]:
        """quiz紐づけ数の多い順(同数はカテゴリ名昇順)でランキングを返す。limit指定時は上位limit件。"""
        ranked = await self._repo.list_ranked_by_quiz_count(limit=limit)
        return [
            CategoryRanking(id=category.id, name=category.name, quiz_count=count)
            for category, count in ranked
        ]
