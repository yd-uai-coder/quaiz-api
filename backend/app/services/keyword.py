from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Keyword
from app.repositories.keyword import KeywordRepository


class KeywordService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = KeywordRepository(session)

    async def list_keywords(self) -> list[Keyword]:
        """キーワード一覧を返す(サジェスト・絞り込み用)。"""
        return await self._repo.list_all()
