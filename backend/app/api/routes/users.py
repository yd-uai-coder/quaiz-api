import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentAdminDep, CurrentUserDep, SessionDep
from app.schemas.user import UserBulkDeleteRequest, UserRead, UserSummary, UserUpdateRequest
from app.services.quiz_attempt import QuizAttemptService
from app.services.user import UserService

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


@router.get("", response_model=list[UserRead])
async def list_users(current_admin: CurrentAdminDep, session: SessionDep) -> list[UserRead]:
    """ADMIN専用の全ユーザー一覧(display_name昇順)。"""
    users = await UserService(session).list_users()
    return [UserRead.model_validate(user) for user in users]


@router.patch("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    """本人またはADMINによるユーザー情報(display_name/role/password)の変更。"""
    await UserService(session).update_user(actor=current_user, target_user_id=user_id, data=payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, current_user: CurrentUserDep, session: SessionDep
) -> None:
    """本人またはADMINによるユーザー削除。"""
    await UserService(session).delete_user(actor=current_user, target_user_id=user_id)


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_users(
    payload: UserBulkDeleteRequest, current_admin: CurrentAdminDep, session: SessionDep
) -> None:
    """ADMIN専用の一括削除。"""
    await UserService(session).bulk_delete_users(user_ids=payload.user_ids)
