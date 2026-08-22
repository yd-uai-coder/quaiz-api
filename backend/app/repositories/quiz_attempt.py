import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
        """(quiz_id, user_id)の回答行をアトミックにUPSERTする。
        SELECTしてから無ければINSERTという実装だと、同一(quiz_id, user_id)への初回リクエストが
        本当に同時に来た場合、両方が「行が無い」と判定してINSERTを試み、片方がユニーク制約
        (uq_quiz_attempts_quiz_id_user_id)違反で失敗しうる。INSERT ... ON CONFLICT DO UPDATEで
        Postgres側にアトミックに処理させることでこの競合を防ぐ。
        """
        update_values: dict[str, Any] = {"corrected": corrected, "updated_at": func.now()}
        if favorite is not None:
            update_values["is_favorite"] = favorite
        if review is not None:
            update_values["review"] = review

        stmt = (
            pg_insert(QuizAttempt)
            .values(
                quiz_id=quiz_id,
                user_id=user_id,
                corrected=corrected,
                is_favorite=favorite or False,
                review=review,
            )
            .on_conflict_do_update(
                constraint="uq_quiz_attempts_quiz_id_user_id",
                set_=update_values,
            )
            .returning(QuizAttempt)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def count_challenged(self, user_id: uuid.UUID) -> int:
        """ユーザーが挑戦したクイズの件数を数える。"""
        return await self.count(user_id=user_id)

    async def count_corrected(self, user_id: uuid.UUID) -> int:
        """ユーザーが正解したクイズの件数を数える。"""
        return await self.count(user_id=user_id, corrected=True)
