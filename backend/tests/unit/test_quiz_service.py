import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category, DifficultyLevel
from app.schemas.quiz import QuizUpdateOption
from app.schemas.quiz_generation import GeneratedOption, GeneratedQuiz
from app.services import quiz as quiz_service_module
from app.services.errors import (
    CategoryNotFoundError,
    DifficultyLevelNotFoundError,
    QuizGenerationFailedError,
    QuizNotFoundError,
    QuizPermissionDeniedError,
    QuizValidationError,
)
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


async def _create_category(session: AsyncSession, name: str = "地理") -> Category:
    category = Category(name=name)
    session.add(category)
    await session.commit()
    return category


async def _create_difficulty_level(
    session: AsyncSession,
    name: str = "超簡単",
    description: str = "誰でも分かる問題。",
    level: int = 1,
) -> DifficultyLevel:
    difficulty_level = DifficultyLevel(name=name, description=description, level=level)
    session.add(difficulty_level)
    await session.commit()
    return difficulty_level


async def _create_user(session: AsyncSession, email: str = "creator@example.com"):
    return await UserService(session).create_user(email=email, password="s3cret")


async def test_generate_quiz_persists_generated_quiz(db_session: AsyncSession, monkeypatch) -> None:
    category = await _create_category(db_session)
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session)
    generated = _valid_generated_quiz()
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": generated, "validation_errors": []}),
    )

    quiz = await QuizService(db_session).generate_quiz(
        category_id=category.id,
        difficulty_level_id=difficulty_level.id,
        keyword_texts=["日本", "首都"],
        created_by_id=user.id,
    )

    assert quiz.title == "日本の首都"
    assert len(quiz.options) == 4
    assert quiz.category.name == "地理"
    assert quiz.difficulty_level.name == "超簡単"
    assert {k.keyword for k in quiz.keywords} == {"日本", "首都"}


async def test_generate_quiz_raises_for_unknown_category(
    db_session: AsyncSession, monkeypatch
) -> None:
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session)
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": _valid_generated_quiz(), "validation_errors": []}),
    )

    with pytest.raises(CategoryNotFoundError):
        await QuizService(db_session).generate_quiz(
            category_id=user.id,
            difficulty_level_id=difficulty_level.id,
            keyword_texts=[],
            created_by_id=user.id,
        )


async def test_generate_quiz_raises_for_unknown_difficulty_level(
    db_session: AsyncSession, monkeypatch
) -> None:
    category = await _create_category(db_session)
    user = await _create_user(db_session)
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": _valid_generated_quiz(), "validation_errors": []}),
    )

    with pytest.raises(DifficultyLevelNotFoundError):
        await QuizService(db_session).generate_quiz(
            category_id=category.id,
            difficulty_level_id=uuid.uuid4(),
            keyword_texts=[],
            created_by_id=user.id,
        )


async def test_generate_quiz_assigns_random_difficulty_when_omitted(
    db_session: AsyncSession, monkeypatch
) -> None:
    category = await _create_category(db_session)
    for level_id in range(1, 6):
        await _create_difficulty_level(
            db_session, name=f"レベル{level_id}", description="説明", level=level_id
        )
    user = await _create_user(db_session)
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": _valid_generated_quiz(), "validation_errors": []}),
    )

    quiz = await QuizService(db_session).generate_quiz(
        category_id=category.id,
        difficulty_level_id=None,
        keyword_texts=[],
        created_by_id=user.id,
    )

    assert 1 <= quiz.difficulty_level.level <= 5


async def test_generate_quiz_raises_when_validation_never_succeeds(
    db_session: AsyncSession, monkeypatch
) -> None:
    category = await _create_category(db_session)
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session)
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": None, "validation_errors": ["生成に失敗しました"]}),
    )

    with pytest.raises(QuizGenerationFailedError):
        await QuizService(db_session).generate_quiz(
            category_id=category.id,
            difficulty_level_id=difficulty_level.id,
            keyword_texts=[],
            created_by_id=user.id,
        )


async def _generate_quiz(db_session: AsyncSession, monkeypatch, **overrides):
    category = await _create_category(db_session)
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session, email=overrides.pop("email", "creator2@example.com"))
    generated = _valid_generated_quiz()
    monkeypatch.setattr(
        quiz_service_module,
        "get_quiz_workflow",
        lambda: FakeWorkflow({"quiz_data": generated, "validation_errors": []}),
    )
    quiz = await QuizService(db_session).generate_quiz(
        category_id=category.id,
        difficulty_level_id=difficulty_level.id,
        keyword_texts=overrides.pop("keyword_texts", []),
        created_by_id=user.id,
    )
    return quiz, user


async def test_get_quiz_includes_my_attempt_when_present(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _generate_quiz(db_session, monkeypatch)
    await QuizAttemptService(db_session).submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=True,
        favorite=True,
        review=None,
    )

    result = await QuizService(db_session).get_quiz(quiz.id, user_id=user.id)

    assert result.my_attempt is not None
    assert result.my_attempt.corrected is True
    assert result.my_attempt.is_favorite is True


async def test_get_quiz_raises_for_unknown_id(db_session: AsyncSession, monkeypatch) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch)

    with pytest.raises(QuizNotFoundError):
        await QuizService(db_session).get_quiz(quiz.category.id, user_id=None)


async def test_list_quizzes_filters_by_category(db_session: AsyncSession, monkeypatch) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch, keyword_texts=["日本", "首都"])
    other_category = await _create_category(db_session, name="歴史")

    items, total = await QuizService(db_session).list_quizzes(
        category_id=other_category.id,
        keyword=None,
        user_id=None,
        favorite_only=False,
        corrected_only=False,
        page=1,
        limit=20,
    )

    assert total == 0
    assert items == []

    items, total = await QuizService(db_session).list_quizzes(
        category_id=quiz.category.id,
        keyword=None,
        user_id=None,
        favorite_only=False,
        corrected_only=False,
        page=1,
        limit=20,
    )
    assert total == 1
    assert items[0].id == quiz.id
    assert {k.keyword for k in items[0].keywords} == {"日本", "首都"}


async def test_list_quizzes_includes_my_attempt_when_present(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _generate_quiz(db_session, monkeypatch)
    other_user = await _create_user(db_session, email="other@example.com")
    await QuizAttemptService(db_session).submit_attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        corrected=True,
        favorite=True,
        review=None,
    )

    items, _ = await QuizService(db_session).list_quizzes(
        category_id=None,
        keyword=None,
        user_id=user.id,
        favorite_only=False,
        corrected_only=False,
        page=1,
        limit=20,
    )
    assert items[0].my_attempt is not None
    assert items[0].my_attempt.corrected is True
    assert items[0].my_attempt.is_favorite is True

    items, _ = await QuizService(db_session).list_quizzes(
        category_id=None,
        keyword=None,
        user_id=other_user.id,
        favorite_only=False,
        corrected_only=False,
        page=1,
        limit=20,
    )
    assert items[0].my_attempt is None

    items, _ = await QuizService(db_session).list_quizzes(
        category_id=None,
        keyword=None,
        user_id=None,
        favorite_only=False,
        corrected_only=False,
        page=1,
        limit=20,
    )
    assert items[0].my_attempt is None


async def test_update_quiz_replaces_fields_and_options(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _generate_quiz(db_session, monkeypatch)

    updated = await QuizService(db_session).update_quiz(
        quiz.id,
        title="改題",
        question="改訂後の問題文",
        commentary="改訂後の解説",
        options=[
            QuizUpdateOption(content="A", is_correct=True),
            QuizUpdateOption(content="B", is_correct=False),
        ],
        user_id=user.id,
        is_admin=False,
    )

    assert updated.title == "改題"
    assert len(updated.options) == 2


async def test_update_quiz_raises_without_correct_option(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, user = await _generate_quiz(db_session, monkeypatch)

    with pytest.raises(QuizValidationError):
        await QuizService(db_session).update_quiz(
            quiz.id,
            title="改題",
            question="改訂後の問題文",
            commentary="改訂後の解説",
            options=[
                QuizUpdateOption(content="A", is_correct=False),
                QuizUpdateOption(content="B", is_correct=False),
            ],
            user_id=user.id,
            is_admin=False,
        )


async def test_update_quiz_raises_for_non_creator_non_admin(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch)
    other_user = await _create_user(db_session, email="other-editor@example.com")

    with pytest.raises(QuizPermissionDeniedError):
        await QuizService(db_session).update_quiz(
            quiz.id,
            title="改題",
            question="改訂後の問題文",
            commentary="改訂後の解説",
            options=[
                QuizUpdateOption(content="A", is_correct=True),
                QuizUpdateOption(content="B", is_correct=False),
            ],
            user_id=other_user.id,
            is_admin=False,
        )


async def test_update_quiz_allows_admin_even_if_not_creator(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch)
    admin_user = await _create_user(db_session, email="admin-editor@example.com")

    updated = await QuizService(db_session).update_quiz(
        quiz.id,
        title="改題",
        question="改訂後の問題文",
        commentary="改訂後の解説",
        options=[
            QuizUpdateOption(content="A", is_correct=True),
            QuizUpdateOption(content="B", is_correct=False),
        ],
        user_id=admin_user.id,
        is_admin=True,
    )

    assert updated.title == "改題"


async def test_delete_quiz_removes_it(db_session: AsyncSession, monkeypatch) -> None:
    quiz, user = await _generate_quiz(db_session, monkeypatch)

    await QuizService(db_session).delete_quiz(quiz.id, user_id=user.id, is_admin=False)

    with pytest.raises(QuizNotFoundError):
        await QuizService(db_session).get_quiz(quiz.id, user_id=None)


async def test_delete_quiz_raises_for_non_creator_non_admin(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch)
    other_user = await _create_user(db_session, email="other-deleter@example.com")

    with pytest.raises(QuizPermissionDeniedError):
        await QuizService(db_session).delete_quiz(quiz.id, user_id=other_user.id, is_admin=False)


async def test_delete_quiz_allows_admin_even_if_not_creator(
    db_session: AsyncSession, monkeypatch
) -> None:
    quiz, _ = await _generate_quiz(db_session, monkeypatch)
    admin_user = await _create_user(db_session, email="admin-deleter@example.com")

    await QuizService(db_session).delete_quiz(quiz.id, user_id=admin_user.id, is_admin=True)

    with pytest.raises(QuizNotFoundError):
        await QuizService(db_session).get_quiz(quiz.id, user_id=None)
