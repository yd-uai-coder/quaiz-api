from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.user import UserRead, UserSummary
from app.services.quiz_attempt import QuizAttemptService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/profile", response_model=UserRead)
async def read_current_user(current_user: CurrentUserDep) -> UserRead:
    """ログイン中ユーザー自身のプロフィール(role含む)を返す。"""
    return UserRead.model_validate(current_user)


@router.get("/profile/summary", response_model=UserSummary)
async def read_current_user_summary(
    current_user: CurrentUserDep, session: SessionDep
) -> UserSummary:
    """マイページ用の集計(挑戦数・正解数)を返す。"""
    challenged, corrected = await QuizAttemptService(session).get_summary(current_user.id)
    return UserSummary(challenged_count=challenged, corrected_count=corrected)
