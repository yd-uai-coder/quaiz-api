import uuid
from collections.abc import Sequence
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quiz import Keyword, Quiz, QuizAttempt, QuizOption
from app.repositories.base import CRUDRepository


class QuizRepository(CRUDRepository[Quiz]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Quiz)

    def _default_options(self) -> Sequence[Any]:
        """category/difficulty_level/keywords/optionsを常に一括eager loadする。"""
        return (
            selectinload(Quiz.category),
            selectinload(Quiz.difficulty_level),
            selectinload(Quiz.keywords),
            selectinload(Quiz.options),
        )

    async def create(
        self,
        *,
        title: str,
        question: str,
        commentary: str,
        category_id: uuid.UUID,
        created_by_id: uuid.UUID,
        difficulty_level_id: uuid.UUID,
        options: list[tuple[str, bool]],
        keywords: list[Keyword],
    ) -> Quiz:
        """生成されたクイズ本体・選択肢・キーワード紐付けをまとめて新規作成する。"""
        quiz = Quiz(
            title=title,
            question=question,
            commentary=commentary,
            category_id=category_id,
            created_by_id=created_by_id,
            difficulty_level_id=difficulty_level_id,
            options=[
                QuizOption(content=content, is_correct=is_correct)
                for content, is_correct in options
            ],
            keywords=keywords,
        )
        self._session.add(quiz)
        await self._session.flush()
        return quiz

    async def list_with_filters(
        self,
        *,
        category_id: uuid.UUID | None,
        keyword: str | None,
        user_id: uuid.UUID | None,
        mine: bool,
        favorite_only: bool,
        corrected: bool | None,
        sort_by: Literal["created_at", "updated_at"],
        page: int,
        limit: int,
    ) -> tuple[list[Quiz], int]:
        """カテゴリ/キーワード/自分の投稿/お気に入り/正解状態で絞り込みつつクイズをページング取得する。"""
        query = self._select()
        count_query = select(func.count(func.distinct(Quiz.id))).select_from(Quiz)

        if category_id is not None:
            query = query.where(Quiz.category_id == category_id)
            count_query = count_query.where(Quiz.category_id == category_id)

        if keyword:
            query = query.join(Quiz.keywords).where(Keyword.keyword == keyword)
            count_query = count_query.join(Quiz.keywords).where(Keyword.keyword == keyword)

        if mine and user_id is not None:
            query = query.where(Quiz.created_by_id == user_id)
            count_query = count_query.where(Quiz.created_by_id == user_id)

        if (favorite_only or corrected is not None) and user_id is not None:
            query = query.join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id).where(
                QuizAttempt.user_id == user_id
            )
            count_query = count_query.join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id).where(
                QuizAttempt.user_id == user_id
            )
            if favorite_only:
                query = query.where(QuizAttempt.is_favorite.is_(True))
                count_query = count_query.where(QuizAttempt.is_favorite.is_(True))
            if corrected is not None:
                query = query.where(QuizAttempt.corrected.is_(corrected))
                count_query = count_query.where(QuizAttempt.corrected.is_(corrected))

        if sort_by == "updated_at":
            query = query.order_by(Quiz.updated_at.desc())
        else:
            query = query.order_by(Quiz.created_at.desc(), Quiz.updated_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        total = (await self._session.execute(count_query)).scalar_one()
        result = await self._session.execute(query)
        return list(result.scalars().unique().all()), total

    async def replace_options(self, quiz: Quiz, options: list[tuple[str, bool]]) -> None:
        """既存の選択肢を全て置き換える(cascade delete-orphanで古い行は削除される)。"""
        quiz.options.clear()
        for content, is_correct in options:
            quiz.options.append(QuizOption(content=content, is_correct=is_correct))
        await self._session.flush()
