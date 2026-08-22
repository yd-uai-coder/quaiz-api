import asyncio
import random
import uuid
from typing import Literal

from google.genai.errors import APIError as GoogleAPIError
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from tavily import UsageLimitExceededError as TavilyUsageLimitExceededError

from app.ai.graph.workflow import get_quiz_workflow
from app.models.quiz import Quiz
from app.repositories.category import CategoryRepository
from app.repositories.difficulty_level import DifficultyLevelRepository
from app.repositories.keyword import KeywordRepository
from app.repositories.quiz import QuizRepository
from app.schemas.quiz import QuizAttemptRead, QuizDetail, QuizListItem, QuizRead, QuizUpdateOption
from app.services.errors import (
    CategoryNotFoundError,
    DifficultyLevelNotFoundError,
    QuizGenerationFailedError,
    QuizNotFoundError,
    QuizPermissionDeniedError,
    QuizValidationError,
)
from app.services.quiz_attempt import QuizAttemptService
from app.services.rate_limit import RATE_LIMIT_MESSAGE, QuizGenerationRateLimitExceededError

MAX_WORKFLOW_RETRIES = 3
_WORKFLOW_RETRY_DELAY_SECONDS = 1.0


def _is_quota_exceeded(exc: Exception) -> bool:
    """Gemini/Tavilyのレート制限・クォータ超過エラーかどうかを判定する。"""
    if isinstance(exc, TavilyUsageLimitExceededError):
        return True
    if isinstance(exc, GoogleAPIError):
        if getattr(exc, "code", None) == 429:
            return True
        message = str(exc)
        return any(token in message for token in ("429", "RESOURCE_EXHAUSTED", "quota"))
    return False


async def _invoke_workflow_with_retry(workflow: CompiledStateGraph, initial_state: dict) -> dict:
    """クォータ超過は即座にQuizGenerationRateLimitExceededErrorへ変換し、
    それ以外の例外はMAX_WORKFLOW_RETRIES回までリトライする。
    """
    last_error: Exception | None = None
    for attempt in range(MAX_WORKFLOW_RETRIES):
        try:
            return await workflow.ainvoke(initial_state)
        except Exception as exc:
            if _is_quota_exceeded(exc):
                raise QuizGenerationRateLimitExceededError(RATE_LIMIT_MESSAGE) from exc
            last_error = exc
            if attempt < MAX_WORKFLOW_RETRIES - 1:
                await asyncio.sleep(_WORKFLOW_RETRY_DELAY_SECONDS)
    raise QuizGenerationFailedError("クイズの生成に失敗しました") from last_error


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)
        self._categories = CategoryRepository(session)
        self._difficulty_levels = DifficultyLevelRepository(session)
        self._keywords = KeywordRepository(session)
        self._attempts = QuizAttemptService(session)

    async def generate_quiz(
        self,
        *,
        category_id: uuid.UUID,
        difficulty_level_id: uuid.UUID | None,
        keyword_texts: list[str],
        created_by_id: uuid.UUID,
    ) -> QuizDetail:
        """LangGraphでクイズを生成し、成功したらDBへ保存する(失敗時は例外を送出)。
        difficulty_level_idが未指定の場合はランダムな難易度を採番する。
        """
        category = await self._categories.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundError(f"Category {category_id} not found")

        if difficulty_level_id is None:
            levels = await self._difficulty_levels.list_all()
            difficulty_level = random.choice(levels)
        else:
            difficulty_level = await self._difficulty_levels.get_by_id(difficulty_level_id)
            if difficulty_level is None:
                raise DifficultyLevelNotFoundError(
                    f"DifficultyLevel {difficulty_level_id} not found"
                )

        workflow = get_quiz_workflow()
        result = await _invoke_workflow_with_retry(
            workflow,
            {
                "category": category.name,
                "keywords": keyword_texts,
                "difficulty_name": difficulty_level.name,
                "difficulty_description": difficulty_level.description,
                "question_data": None,
                "search_results": [],
                "quiz_data": None,
                "validation_errors": [],
                "attempt": 0,
            },
        )

        if result["validation_errors"] or result["quiz_data"] is None:
            raise QuizGenerationFailedError(
                "; ".join(result["validation_errors"]) or "クイズの生成に失敗しました"
            )

        generated = result["quiz_data"]
        keywords = [await self._keywords.get_or_create(text) for text in keyword_texts]

        quiz = await self._quizzes.create(
            title=generated.title,
            question=generated.question,
            commentary=generated.commentary,
            category_id=category.id,
            created_by_id=created_by_id,
            difficulty_level_id=difficulty_level.id,
            options=[(option.content, option.is_correct) for option in generated.options],
            keywords=keywords,
        )
        await self._session.commit()

        quiz = await self._quizzes.get_by_id(quiz.id)
        return self._to_quiz_detail(quiz)

    async def get_quiz(self, quiz_id: uuid.UUID, *, user_id: uuid.UUID | None) -> QuizRead:
        """クイズ詳細を取得する。user_idがあれば本人の回答状況(my_attempt)も付与する。"""
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found")

        attempt = None
        if user_id is not None:
            attempt = await self._attempts.get_attempt(quiz_id=quiz_id, user_id=user_id)
        return self._to_quiz_read(quiz, attempt=attempt)

    async def list_quizzes(
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
    ) -> tuple[list[QuizListItem], int]:
        """条件に合うクイズをページング付きで一覧取得する。"""
        quizzes, total = await self._quizzes.list_with_filters(
            category_id=category_id,
            keyword=keyword,
            user_id=user_id,
            mine=mine,
            favorite_only=favorite_only,
            corrected=corrected,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

        # ユーザー認証時はお気に入りと過去の回答結果の情報を取得
        attempts_by_quiz_id: dict[uuid.UUID, QuizAttemptRead] = {}
        if user_id is not None and quizzes:
            attempts_by_quiz_id = await self._attempts.get_attempts_by_quiz_id(
                user_id=user_id, quiz_ids=[quiz.id for quiz in quizzes]
            )

        # クイズ一覧の作成(未認証の場合my_attemptにはNoneが入る)
        items = [
            QuizListItem.model_validate(quiz).model_copy(
                update={"my_attempt": attempts_by_quiz_id.get(quiz.id)}
            )
            for quiz in quizzes
        ]
        return items, total

    async def update_quiz(
        self,
        quiz_id: uuid.UUID,
        *,
        options: list[QuizUpdateOption],
        user_id: uuid.UUID,
        is_admin: bool,
    ) -> None:
        """作成者本人または管理者によるクイズ編集。選択肢一式を丸ごと置き換える。"""
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found")
        if not is_admin and quiz.created_by_id != user_id:
            raise QuizPermissionDeniedError("この操作を行う権限がありません。")
        if not any(option.is_correct for option in options):
            raise QuizValidationError("エラー：正解の選択肢が含まれていません。")

        existing_option_ids = {option.id for option in quiz.options}
        for option in options:
            if option.id is not None and option.id not in existing_option_ids:
                raise QuizValidationError(
                    "エラー：選択肢の情報が最新の状態と一致しません。ページを再読み込みしてください。"
                )

        await self._quizzes.replace_options(quiz, [(o.content, o.is_correct) for o in options])
        await self._session.commit()

    async def delete_quiz(self, quiz_id: uuid.UUID, *, user_id: uuid.UUID, is_admin: bool) -> None:
        """作成者本人または管理者によるクイズ削除。"""
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found")
        if not is_admin and quiz.created_by_id != user_id:
            raise QuizPermissionDeniedError("この操作を行う権限がありません。")
        await self._quizzes.delete(quiz)
        await self._session.commit()

    @staticmethod
    def _to_quiz_detail(quiz: Quiz) -> QuizDetail:
        """ORMのQuizエンティティから、生成直後のレスポンス用に必要最小限のQuizDetailスキーマを組み立てる。"""
        return QuizDetail(
            id=quiz.id,
            title=quiz.title,
            question=quiz.question,
            commentary=quiz.commentary,
            difficulty_level=quiz.difficulty_level,
            options=list(quiz.options),
        )

    @staticmethod
    def _to_quiz_read(quiz: Quiz, *, attempt: QuizAttemptRead | None) -> QuizRead:
        """ORMのQuizエンティティ(+任意の回答状態)からQuizReadスキーマを組み立てる。"""
        return QuizRead(
            **QuizService._to_quiz_detail(quiz).model_dump(),
            category=quiz.category,
            keywords=list(quiz.keywords),
            created_at=quiz.created_at,
            updated_at=quiz.updated_at,
            my_attempt=attempt,
        )
