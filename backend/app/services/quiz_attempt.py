import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.quiz import QuizRepository
from app.repositories.quiz_attempt import QuizAttemptRepository
from app.schemas.quiz import QuizAttemptRead, QuizAttemptResult
from app.services.errors import QuizNotFoundError


class QuizAttemptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)
        self._attempts = QuizAttemptRepository(session)

    async def submit_attempt(
        self,
        *,
        quiz_id: uuid.UUID,
        user_id: uuid.UUID,
        corrected: bool,
        favorite: bool | None,
        review: str | None,
    ) -> QuizAttemptResult:
        """正誤(クライアント判定済み)・お気に入り・レビューを回答状態としてUPSERTして結果を返す。"""
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found")

        attempt = await self._attempts.upsert(
            quiz_id=quiz_id,
            user_id=user_id,
            corrected=corrected,
            favorite=favorite,
            review=review,
        )
        await self._session.commit()

        return QuizAttemptResult(corrected=attempt.corrected, is_favorite=attempt.is_favorite)

    async def get_attempt(
        self, *, quiz_id: uuid.UUID, user_id: uuid.UUID
    ) -> QuizAttemptRead | None:
        """特定ユーザーの特定クイズに対する回答状態を1件取得する。"""
        attempt = await self._attempts.get_for_user_and_quiz(quiz_id=quiz_id, user_id=user_id)
        return QuizAttemptRead.model_validate(attempt) if attempt else None

    async def get_attempts_by_quiz_id(
        self, *, user_id: uuid.UUID, quiz_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, QuizAttemptRead]:
        """指定ユーザーの、指定クイズ群に対する回答状態をquiz_idをキーにした辞書で返す(一覧のN+1回避用)。"""
        attempts = await self._attempts.list_for_user_and_quizzes(
            user_id=user_id, quiz_ids=quiz_ids
        )
        return {attempt.quiz_id: QuizAttemptRead.model_validate(attempt) for attempt in attempts}

    async def get_summary(self, user_id: uuid.UUID) -> tuple[int, int]:
        """マイページ用の集計値(挑戦数, 正解数)を返す。"""
        challenged = await self._attempts.count_challenged(user_id)
        corrected = await self._attempts.count_corrected(user_id)
        return challenged, corrected
