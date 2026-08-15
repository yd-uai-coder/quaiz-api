import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import QuizAttempt
from app.repositories.base import CRUDRepository


class QuizAttemptRepository(CRUDRepository[QuizAttempt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuizAttempt)

    async def get_for_user_and_quiz(
        self, *, quiz_id: uuid.UUID, user_id: uuid.UUID
    ) -> QuizAttempt | None:
        """特定ユーザーの特定クイズに対する回答状態を1件取得する。"""
        return await self.find_one(quiz_id=quiz_id, user_id=user_id)

    async def upsert(
        self,
        *,
        quiz_id: uuid.UUID,
        user_id: uuid.UUID,
        is_correct: bool,
        favorite: bool | None,
        review: str | None,
    ) -> QuizAttempt:
        """(quiz_id, user_id)の回答行があれば更新、なければ新規作成する(UPSERT)。"""
        attempt = await self.get_for_user_and_quiz(quiz_id=quiz_id, user_id=user_id)
        if attempt is None:
            attempt = QuizAttempt(
                quiz_id=quiz_id,
                user_id=user_id,
                is_correct=is_correct,
                is_favorite=favorite or False,
                review=review,
            )
            self._session.add(attempt)
        else:
            attempt.is_correct = is_correct
            if favorite is not None:
                attempt.is_favorite = favorite
            if review is not None:
                attempt.review = review
        await self._session.flush()
        return attempt

    async def count_challenged(self, user_id: uuid.UUID) -> int:
        """ユーザーが挑戦したクイズの件数を数える。"""
        return await self.count(user_id=user_id)

    async def count_corrected(self, user_id: uuid.UUID) -> int:
        """ユーザーが正解したクイズの件数を数える。"""
        return await self.count(user_id=user_id, is_correct=True)
