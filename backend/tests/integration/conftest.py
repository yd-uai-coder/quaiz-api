# DATABASE_URLをテスト専用DB(<元のDB名>_test)へリダイレクトする処理は、
# app.core.databaseを最初にimportするルートのtests/conftest.pyで行っている
# (このファイルより先にpytestがロードするため。詳細はそちらのコメント参照)。
# ここではリダイレクト後のDATABASE_URLからテスト専用DB名を再導出し、
# そのDBがまだ無ければ作成する。
import os

from collections.abc import AsyncGenerator  # noqa: E402

import asyncpg  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.infrastructure.redis import get_redis_pool  # noqa: E402
from app.main import app  # noqa: E402

_DSN_BASE, _, _TEST_DB_NAME = os.environ["DATABASE_URL"].rpartition("/")


async def _ensure_test_database_exists() -> None:
    """テスト専用DBがまだ無ければ作成する(初回のみ実行される)。"""
    admin_dsn = _DSN_BASE.replace("postgresql+asyncpg://", "postgresql://") + "/postgres"
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Exercises the full FastAPI -> PostgreSQL -> Redis stack.

    DATABASE_URL はこのファイル冒頭で専用のテストDB(quaiz_app_test)へ
    差し替えられているため、開発用DBのデータには一切触れない。
    """
    # get_redis_pool() is process-lifetime-cached, but pytest-asyncio gives each
    # test function its own event loop; drop the cache so a fresh pool binds to
    # the loop that is actually running for this test.
    get_redis_pool.cache_clear()

    await _ensure_test_database_exists()

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
