from fastapi import APIRouter, Query

from app.api.deps import RedisDep, SessionDep
from app.schemas.category import CategoryRanking, CategoryRead
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(session: SessionDep, redis: RedisDep) -> list[CategoryRead]:
    """カテゴリ一覧を返す。認証不要。"""
    categories = await CategoryService(session, redis).list_categories()
    return [CategoryRead.model_validate(category) for category in categories]


@router.get("/ranking", response_model=list[CategoryRanking])
async def list_category_ranking(
    session: SessionDep,
    redis: RedisDep,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> list[CategoryRanking]:
    """クイズ紐づけ数の多い順(同数はカテゴリ名昇順)でランキングを返す。認証不要。limit指定時は上位limit件のみ。"""
    return await CategoryService(session, redis).list_ranking(limit=limit)
