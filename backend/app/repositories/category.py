from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category
from app.repositories.base import CRUDRepository


class CategoryRepository(CRUDRepository[Category]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Category)

    async def list_all(self) -> list[Category]:
        """カテゴリを名前順で全件取得する。"""
        return await super().list_all(order_by=Category.name)
