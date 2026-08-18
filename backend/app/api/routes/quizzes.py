import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import (
    CurrentUserDep,
    OptionalCurrentUserDep,
    RedisDep,
    SessionDep,
)
from app.models.user import UserRole
from app.schemas.quiz import (
    QuizAttemptRequest,
    QuizAttemptResult,
    QuizGenerateRequest,
    QuizListResponse,
    QuizRead,
    QuizUpdateRequest,
)
from app.services.quiz import QuizService
from app.services.quiz_attempt import QuizAttemptService
from app.services.rate_limit import QuizGenerationRateLimiter

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("", response_model=QuizListResponse)
async def list_quizzes(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,  # 未ログインならNoneを返す
    category_id: uuid.UUID | None = None,
    keyword: str | None = None,
    favorite: bool = False,
    corrected: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> QuizListResponse:
    """クイズ一覧を条件検索する。favorite/correctedはログイン時のみ指定可能。"""
    if (favorite or corrected) and current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    items, total = await QuizService(session).list_quizzes(
        category_id=category_id,
        keyword=keyword,
        user_id=current_user.id if current_user else None,
        favorite_only=favorite,
        corrected_only=corrected,
        page=page,
        limit=limit,
    )
    return QuizListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{quiz_id}", response_model=QuizRead)
async def get_quiz(
    quiz_id: uuid.UUID, session: SessionDep, current_user: OptionalCurrentUserDep
) -> QuizRead:
    """クイズ詳細(選択肢込み)を返す。認証不要だがログイン時は自分の回答状況も含む。"""
    return await QuizService(session).get_quiz(
        quiz_id, user_id=current_user.id if current_user else None
    )


@router.post("/generate", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    payload: QuizGenerateRequest,
    session: SessionDep,
    redis: RedisDep,
    current_user: CurrentUserDep,
) -> QuizRead:
    """ログインユーザーがカテゴリ・キーワードを指定してクイズをAI生成する。

    USERロールは1時間5回・1日10回のレート制限がかかる(ADMINは無制限)。
    """
    if current_user.role != UserRole.ADMIN:
        await QuizGenerationRateLimiter(redis).check_and_increment(current_user.id)

    return await QuizService(session).generate_quiz(
        category_id=payload.category_id,
        difficulty_level_id=payload.difficulty_level_id,
        keyword_texts=[k.strip() for k in payload.keywords if k.strip()],
        created_by_id=current_user.id,
    )


@router.patch("/{quiz_id}", response_model=QuizRead)
async def update_quiz(
    quiz_id: uuid.UUID,
    payload: QuizUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> QuizRead:
    """作成者本人または管理者がクイズ本文と選択肢を編集する。"""
    return await QuizService(session).update_quiz(
        quiz_id,
        title=payload.title,
        question=payload.question,
        commentary=payload.commentary,
        options=payload.options,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep
) -> None:
    """作成者本人または管理者がクイズを削除する。"""
    await QuizService(session).delete_quiz(
        quiz_id, user_id=current_user.id, is_admin=current_user.role == UserRole.ADMIN
    )


@router.post("/{quiz_id}/attempts", response_model=QuizAttemptResult)
async def submit_attempt(
    quiz_id: uuid.UUID,
    payload: QuizAttemptRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> QuizAttemptResult:
    """回答結果、お気に入り、レビューの登録"""
    return await QuizAttemptService(session).submit_attempt(
        quiz_id=quiz_id,
        user_id=current_user.id,
        corrected=payload.corrected,
        favorite=payload.favorite,
        review=payload.review,
    )
