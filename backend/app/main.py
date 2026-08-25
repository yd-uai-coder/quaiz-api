from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.error_handlers import register_error_handlers
from app.api.routes import api_router
from app.core.config import settings
from app.core.database import engine
from app.infrastructure.redis import get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # サーバー起動後にSQLAlchemyのEngineを終了する
    await engine.dispose()


_is_production = settings.ENVIRONMENT == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

# app/api/routes/__init__.pyのルーティング設定を一括読み込み、prefixの一括管理
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": settings.PROJECT_NAME, "status": "ok"}


@app.get("/health")
async def health() -> dict[str, object]:
    db_ok = await _check_database()
    redis_ok = await _check_redis()
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
    }


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    client = get_redis_client()
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
