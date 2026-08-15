from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.category import CategoryRead
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(session: SessionDep) -> list[CategoryRead]:
    """カテゴリ一覧を返す。認証不要。"""
    categories = await CategoryService(session).list_categories()
    return [CategoryRead.model_validate(category) for category in categories]
