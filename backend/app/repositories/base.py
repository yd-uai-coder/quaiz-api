import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base


class CRUDRepository[ModelType: Base]:
    """単一テーブルの共通データアクセス処理。各リポジトリで継承して使う。"""

    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        self._session = session
        self._model = model

    def _default_options(self) -> Sequence[Any]:
        """eager loadのデフォルト設定。関連をまとめて読みたいリポジトリでオーバーライドする。"""
        return ()

    def _select(self) -> Select:
        """_default_optionsを適用した基本SELECT文。"""
        return select(self._model).options(*self._default_options())

    async def get_by_id(self, obj_id: uuid.UUID) -> ModelType | None:
        """PKで1件取得する(_default_optionsのeager loadを適用)。"""
        result = await self._session.execute(self._select().where(self._model.id == obj_id))
        return result.scalar_one_or_none()

    async def find_one(self, **filters: Any) -> ModelType | None:
        """任意カラムの完全一致条件で1件検索する(_default_optionsのeager loadを適用)。"""
        result = await self._session.execute(self._select().filter_by(**filters))
        return result.scalar_one_or_none()

    async def list_all(self, *, order_by: Any | None = None) -> list[ModelType]:
        """全件取得する(order_by指定時はその列でソートする)。"""
        query = self._select()
        if order_by is not None:
            query = query.order_by(order_by)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_or_create(
        self, *, lookup: dict[str, Any], defaults: dict[str, Any] | None = None
    ) -> ModelType:
        """lookup条件で検索し、なければlookup+defaultsで新規作成する。"""
        existing = await self.find_one(**lookup)
        if existing is not None:
            return existing
        obj = self._model(**lookup, **(defaults or {}))
        self._session.add(obj)
        await self._session.flush()
        return obj

    async def count(self, **filters: Any) -> int:
        """任意カラムの完全一致条件で件数を数える。"""
        result = await self._session.execute(
            select(func.count()).select_from(self._model).filter_by(**filters)
        )
        return result.scalar_one()

    async def delete(self, obj: ModelType) -> None:
        """取得済みのオブジェクトを削除する。"""
        await self._session.delete(obj)
        await self._session.flush()
