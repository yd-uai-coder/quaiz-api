from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, engine
from app.infrastructure.redis import get_redis_pool
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Exercises the full FastAPI -> PostgreSQL -> Redis stack.

    Requires DATABASE_URL / REDIS_URL to point at live services, e.g. the
    ones started by `docker compose up postgres redis`.
    """
    # get_redis_pool() is process-lifetime-cached, but pytest-asyncio gives each
    # test function its own event loop; drop the cache so a fresh pool binds to
    # the loop that is actually running for this test.
    get_redis_pool.cache_clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Close out this test's pooled connections before its event loop closes;
    # otherwise the next test (fresh event loop) can crash reusing a stale one.
    await engine.dispose()
