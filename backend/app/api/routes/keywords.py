from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.keyword import KeywordRead
from app.services.keyword import KeywordService

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordRead])
async def list_keywords(session: SessionDep) -> list[KeywordRead]:
    """キーワード一覧を返す。認証不要。"""
    keywords = await KeywordService(session).list_keywords()
    return [KeywordRead.model_validate(keyword) for keyword in keywords]
