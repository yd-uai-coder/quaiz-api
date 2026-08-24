from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Keyword
from app.repositories.keyword import KeywordRepository
from app.schemas.keyword import KeywordRanking

_RANKING_CACHE_KEY_PREFIX = "keyword_ranking"
_RANKING_CACHE_TTL_SECONDS = 60

_ranking_list_adapter = TypeAdapter(list[KeywordRanking])


class KeywordService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = KeywordRepository(session)
        self._redis = redis

    async def list_keywords(self) -> list[Keyword]:
        """キーワード一覧を返す(サジェスト・絞り込み用)。"""
        return await self._repo.list_all()

    async def list_ranking(self, *, limit: int | None = None) -> list[KeywordRanking]:
        """quiz紐づけ数の多い順(同数はキーワード名昇順)でランキングを返す。limit指定時は上位limit件。

        頻繁に叩かれる割に厳密なリアルタイム性が不要なため、短TTLのRedisキャッシュを挟む
        (cache-aside)。
        """
        cache_key = f"{_RANKING_CACHE_KEY_PREFIX}:limit={limit}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return _ranking_list_adapter.validate_json(cached)

        ranked = await self._repo.list_ranked_by_quiz_count(limit=limit)
        ranking = [
            KeywordRanking(id=keyword.id, keyword=keyword.keyword, quiz_count=count)
            for keyword, count in ranked
        ]
        await self._redis.set(cache_key, _ranking_list_adapter.dump_json(ranking), ex=_RANKING_CACHE_TTL_SECONDS)
        return ranking
