from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, engine
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Exercises the full FastAPI -> PostgreSQL -> Redis stack.

    Requires DATABASE_URL / REDIS_URL to point at live services, e.g. the
    ones started by `docker compose up postgres redis`.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
