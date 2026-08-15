import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("ENVIRONMENT", "test")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base  # noqa: E402


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """In-memory SQLite session for unit-testing repositories/services."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class FakeRedis:
    """Minimal in-memory stand-in for the subset of redis.asyncio.Redis used across services."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttl[key] = ex

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def exists(self, key: str) -> int:
        return int(key in self._store)

    async def delete(self, key: str) -> int:
        self._ttl.pop(key, None)
        return int(self._store.pop(key, None) is not None)

    async def incr(self, key: str) -> int:
        value = int(self._store.get(key, "0")) + 1
        self._store[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self._store:
            return False
        self._ttl[key] = seconds
        return True


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
