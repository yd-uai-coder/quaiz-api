from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.difficulty_level import DifficultyLevelRead
from app.services.difficulty_level import DifficultyLevelService

router = APIRouter(prefix="/difficulty-levels", tags=["difficulty-levels"])


@router.get("", response_model=list[DifficultyLevelRead])
async def list_difficulty_levels(session: SessionDep) -> list[DifficultyLevelRead]:
    """難易度一覧を返す。認証不要。"""
    levels = await DifficultyLevelService(session).list_difficulty_levels()
    return [DifficultyLevelRead.model_validate(level) for level in levels]
