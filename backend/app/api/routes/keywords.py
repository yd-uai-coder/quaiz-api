from fastapi import APIRouter, Query

from app.api.deps import RedisDep, SessionDep
from app.schemas.keyword import KeywordRanking, KeywordRead
from app.services.keyword import KeywordService

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordRead])
async def list_keywords(session: SessionDep, redis: RedisDep) -> list[KeywordRead]:
    """キーワード一覧を返す。認証不要。"""
    keywords = await KeywordService(session, redis).list_keywords()
    return [KeywordRead.model_validate(keyword) for keyword in keywords]


@router.get("/ranking", response_model=list[KeywordRanking])
async def list_keyword_ranking(
    session: SessionDep,
    redis: RedisDep,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> list[KeywordRanking]:
    """クイズ紐づけ数の多い順(同数はキーワード名昇順)でランキングを返す。認証不要。limit指定時は上位limit件のみ。"""
    return await KeywordService(session, redis).list_ranking(limit=limit)
