import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-api-key")
os.environ.setdefault("ENVIRONMENT", "test")

from collections.abc import AsyncGenerator  # noqa: E402

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
