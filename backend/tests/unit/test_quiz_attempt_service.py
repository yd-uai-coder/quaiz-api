import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category, DifficultyLevel
from app.schemas.quiz_generation import GeneratedOption, GeneratedQuiz
from app.services import quiz as quiz_service_module
from app.services.errors import QuizNotFoundError
from app.services.quiz import QuizService
from app.services.quiz_attempt import QuizAttemptService
from app.services.user import UserService


class FakeWorkflow:
    def __init__(self, result: dict) -> None:
        self._result = result

    async def ainvoke(self, _state: dict) -> dict:
        return self._result


def _valid_generated_quiz() -> GeneratedQuiz:
    return GeneratedQuiz(
        title="日本の首都",
        question="日本の首都はどこでしょう?",
        options=[
            GeneratedOption(content="東京", is_correct=True),
            GeneratedOption(content="大阪", is_correct=False),
            GeneratedOption(content="京都", is_correct=False),
            GeneratedOption(content="札幌", is_correct=False),
        ],
        commentary="日本の首都は東京です。",
    )


async def _create_quiz(db_session: AsyncSession, monkeypatch, email: str):
    category = Category(name="地理")
    difficulty_level = DifficultyLevel(name="超簡単", description="誰でも分かる問題。", level=1)
    db_session.add_all([category, difficulty_level])
    await db_session.commit()
    user = await UserService(db_session).create_user(email=email, password="s3cret")
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": _valid_generated_quiz(), "validation_errors": []}),
    )
    quiz = await QuizService(db_session).generate_quiz(
        category_id=category.id,
        difficulty_level_id=difficulty_level.id,
        keyword_texts=[],
        created_by_id=user.id,
    )
    return quiz, user


async def test_submit_attempt_records_correct_answer(db_session: AsyncSession, monkeypatch) -> None:
    quiz, user = await _create_quiz(db_session, monkeypatch, "answerer@example.com")

    result = await QuizAttemptService(db_session).submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=True,
        favorite=None,
        review=None,
    )

    assert result.corrected is True


async def test_submit_attempt_records_incorrect_answer(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _create_quiz(db_session, monkeypatch, "wrong-answerer@example.com")

    result = await QuizAttemptService(db_session).submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=False,
        favorite=None,
        review=None,
    )

    assert result.corrected is False


async def test_submit_attempt_upserts_same_row_on_retry(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _create_quiz(db_session, monkeypatch, "retry@example.com")
    service = QuizAttemptService(db_session)

    await service.submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=False,
        favorite=None,
        review=None,
    )
    await service.submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=True,
        favorite=True,
        review="覚えた",
    )

    challenged, corrected = await service.get_summary(user.id)
    assert challenged == 1
    assert corrected == 1


async def test_submit_attempt_raises_for_unknown_quiz(db_session: AsyncSession) -> None:
    user = await UserService(db_session).create_user(email="noquiz@example.com", password="s3cret")

    with pytest.raises(QuizNotFoundError):
        await QuizAttemptService(db_session).submit_attempt(
            quiz_id=uuid.uuid4(),
            user_id=user.id,
            corrected=True,
            favorite=None,
            review=None,
        )


async def test_get_summary_counts_challenged_and_corrected(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _create_quiz(db_session, monkeypatch, "summary@example.com")
    service = QuizAttemptService(db_session)

    await service.submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=True,
        favorite=None,
        review=None,
    )

    challenged, corrected = await service.get_summary(user.id)

    assert challenged == 1
    assert corrected == 1
