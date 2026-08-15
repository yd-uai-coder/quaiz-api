import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.repositories.quiz import QuizRepository
from app.repositories.quiz_attempt import QuizAttemptRepository
from app.schemas.quiz import QuizAttemptResult
from app.services.quiz import QuizNotFoundError


class OptionNotFoundError(BadRequestError):
    pass


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
        selected_option_id: uuid.UUID,
        favorite: bool | None,
        review: str | None,
    ) -> QuizAttemptResult:
        """選択肢を採点し、回答状態(正誤・お気に入り・レビュー)をUPSERTして結果を返す。"""
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found")

        selected_option = next((o for o in quiz.options if o.id == selected_option_id), None)
        if selected_option is None:
            raise OptionNotFoundError(f"Option {selected_option_id} not found")

        correct_option = next(o for o in quiz.options if o.is_correct)

        attempt = await self._attempts.upsert(
            quiz_id=quiz_id,
            user_id=user_id,
            is_correct=selected_option.is_correct,
            favorite=favorite,
            review=review,
        )
        await self._session.commit()

        return QuizAttemptResult(
            is_correct=attempt.is_correct,
            correct_option_id=correct_option.id,
            commentary=quiz.commentary,
            is_favorite=attempt.is_favorite,
        )

    async def get_summary(self, user_id: uuid.UUID) -> tuple[int, int]:
        """マイページ用の集計値(挑戦数, 正解数)を返す。"""
        challenged = await self._attempts.count_challenged(user_id)
        corrected = await self._attempts.count_corrected(user_id)
        return challenged, corrected
