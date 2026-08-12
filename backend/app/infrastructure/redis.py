from collections.abc import AsyncGenerator
from functools import lru_cache

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings


@lru_cache
def get_redis_pool() -> ConnectionPool:
    return ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis_client() -> Redis:
    return Redis(connection_pool=get_redis_pool())


async def get_redis() -> AsyncGenerator[Redis]:
    """FastAPI dependency yielding a Redis client bound to the shared pool."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
