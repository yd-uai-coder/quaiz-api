import uuid
from collections.abc import Sequence

from sqlalchemy import select
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

    async def list_for_user_and_quizzes(
        self, *, user_id: uuid.UUID, quiz_ids: Sequence[uuid.UUID]
    ) -> list[QuizAttempt]:
        """指定ユーザーの、指定クイズ群に対する回答状態をまとめて取得する(一覧のN+1回避用)。"""
        if not quiz_ids:
            return []
        result = await self._session.execute(
            select(QuizAttempt).where(
                QuizAttempt.user_id == user_id, QuizAttempt.quiz_id.in_(quiz_ids)
            )
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        quiz_id: uuid.UUID,
        user_id: uuid.UUID,
        corrected: bool,
        favorite: bool | None,
        review: str | None,
    ) -> QuizAttempt:
        """(quiz_id, user_id)の回答行があれば更新、なければ新規作成する(UPSERT)。"""
        attempt = await self.get_for_user_and_quiz(quiz_id=quiz_id, user_id=user_id)
        if attempt is None:
            attempt = QuizAttempt(
                quiz_id=quiz_id,
                user_id=user_id,
                corrected=corrected,
                is_favorite=favorite or False,
                review=review,
            )
            self._session.add(attempt)
        else:
            attempt.corrected = corrected
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
        return await self.count(user_id=user_id, corrected=True)
