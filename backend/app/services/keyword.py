from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Keyword
from app.repositories.keyword import KeywordRepository
from app.schemas.keyword import KeywordRanking


class KeywordService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = KeywordRepository(session)

    async def list_keywords(self) -> list[Keyword]:
        """キーワード一覧を返す(サジェスト・絞り込み用)。"""
        return await self._repo.list_all()

    async def list_ranking(self, *, limit: int | None = None) -> list[KeywordRanking]:
        """quiz紐づけ数の多い順(同数はキーワード名昇順)でランキングを返す。limit指定時は上位limit件。"""
        ranked = await self._repo.list_ranked_by_quiz_count(limit=limit)
        return [
            KeywordRanking(id=keyword.id, keyword=keyword.keyword, quiz_count=count)
            for keyword, count in ranked
        ]
