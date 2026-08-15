from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Keyword
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
