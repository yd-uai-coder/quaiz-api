from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category, Quiz
from app.repositories.base import CRUDRepository


class CategoryRepository(CRUDRepository[Category]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Category)

    async def list_all(self) -> list[Category]:
        """カテゴリを名前順で全件取得する。"""
        return await super().list_all(order_by=Category.name)

    async def list_ranked_by_quiz_count(
        self, *, limit: int | None = None
    ) -> list[tuple[Category, int]]:
        """紐づくクイズ数の多い順(同数はname昇順)でカテゴリを返す。0件のカテゴリも含む。
        limit指定時は上位limit件のみ返す。
        """
        quiz_count = func.count(Quiz.id).label("quiz_count")
        query = (
            select(Category, quiz_count)
            .outerjoin(Quiz, Quiz.category_id == Category.id)
            .group_by(Category.id)
            .order_by(quiz_count.desc(), Category.name.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        return [(row.Category, row.quiz_count) for row in result]
