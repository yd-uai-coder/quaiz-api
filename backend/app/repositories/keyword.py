from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Keyword, quiz_keywords
from app.repositories.base import CRUDRepository


class KeywordRepository(CRUDRepository[Keyword]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Keyword)

    async def list_all(self) -> list[Keyword]:
        """キーワードを50音(文字コード)順で全件取得する。"""
        return await super().list_all(order_by=Keyword.keyword)

    async def get_or_create(self, keyword_text: str) -> Keyword:
        """同名キーワードがあれば返し、なければ新規作成する(クイズ生成時のタグ登録用)。"""
        return await super().get_or_create(lookup={"keyword": keyword_text})

    async def list_ranked_by_quiz_count(
        self, *, limit: int | None = None
    ) -> list[tuple[Keyword, int]]:
        """紐づくクイズ数の多い順(同数はkeyword昇順)でキーワードを返す。0件のキーワードも含む。
        limit指定時は上位limit件のみ返す。
        """
        quiz_count = func.count(quiz_keywords.c.quiz_id).label("quiz_count")
        query = (
            select(Keyword, quiz_count)
            .outerjoin(quiz_keywords, quiz_keywords.c.keyword_id == Keyword.id)
            .group_by(Keyword.id)
            .order_by(quiz_count.desc(), Keyword.keyword.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        return [(row.Keyword, row.quiz_count) for row in result]
