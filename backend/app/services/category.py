from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryRanking

_RANKING_CACHE_KEY_PREFIX = "category_ranking"
_RANKING_CACHE_TTL_SECONDS = 60

_ranking_list_adapter = TypeAdapter(list[CategoryRanking])


class CategoryService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = CategoryRepository(session)
        self._redis = redis

    async def list_categories(self) -> list[Category]:
        """カテゴリ一覧を返す(クイズ生成・絞り込みのドロップダウン用)。"""
        return await self._repo.list_all()

    async def list_ranking(self, *, limit: int | None = None) -> list[CategoryRanking]:
        """quiz紐づけ数の多い順(同数はカテゴリ名昇順)でランキングを返す。limit指定時は上位limit件。

        頻繁に叩かれる割に厳密なリアルタイム性が不要なため、短TTLのRedisキャッシュを挟む
        (cache-aside)。
        """
        cache_key = f"{_RANKING_CACHE_KEY_PREFIX}:limit={limit}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return _ranking_list_adapter.validate_json(cached)

        ranked = await self._repo.list_ranked_by_quiz_count(limit=limit)
        ranking = [
            CategoryRanking(id=category.id, name=category.name, quiz_count=count)
            for category, count in ranked
        ]
        await self._redis.set(cache_key, _ranking_list_adapter.dump_json(ranking), ex=_RANKING_CACHE_TTL_SECONDS)
        return ranking
