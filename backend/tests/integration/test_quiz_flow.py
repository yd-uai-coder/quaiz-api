import itertools
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.graph import nodes
from app.core.database import AsyncSessionLocal
from app.models.quiz import Category, DifficultyLevel
from app.models.user import User, UserCredential, UserRole
from app.schemas.quiz_generation import GeneratedAnswer, GeneratedOption, GeneratedQuestion

pytestmark = pytest.mark.integration


class FakeStructuredLLM:
    def __init__(self, result) -> None:
        self._result = result

    def invoke(self, _prompt):
        return self._result


class FakeLLM:
    """スキーマごとに異なる応答を返すfake(generate_answerは再試行のたびに呼ばれる)。"""

    def __init__(self, *, question: GeneratedQuestion, answers: Iterator[GeneratedAnswer]) -> None:
        self._question = question
        self._answers = answers

    def with_structured_output(self, schema):
        if schema is GeneratedQuestion:
            return FakeStructuredLLM(self._question)
        if schema is GeneratedAnswer:
            return FakeStructuredLLM(next(self._answers))
        raise ValueError(f"unexpected schema: {schema}")


class FakeTavilyTool:
    def invoke(self, _query: dict) -> dict:
        return {"results": []}


def _valid_question() -> GeneratedQuestion:
    return GeneratedQuestion(title="日本の首都", question="日本の首都はどこでしょう?")


def _valid_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        options=[
            GeneratedOption(content="東京", is_correct=True),
            GeneratedOption(content="大阪", is_correct=False),
            GeneratedOption(content="京都", is_correct=False),
            GeneratedOption(content="札幌", is_correct=False),
        ],
        commentary="日本の首都は東京です。",
    )


def _mock_quiz_generation(monkeypatch, *, answers: Iterator[GeneratedAnswer] | None = None) -> None:
    """generate_question/generate_answerのGemini呼び出しとTavily検索をモック化する。"""
    question = _valid_question()
    answers_iter = answers if answers is not None else iter([_valid_answer()])
    monkeypatch.setattr(
        nodes, "get_gemini_llm", lambda **_: FakeLLM(question=question, answers=answers_iter)
    )
    monkeypatch.setattr(nodes, "get_tavily_search_tool", lambda: FakeTavilyTool())


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "s3cret-pass", "full_name": "Tester"},
    )
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "s3cret-pass"}
    )
    return login_response.json()["access_token"]


async def _create_category(name: str = "地理") -> str:
    async with AsyncSessionLocal() as session:
        category = Category(name=name)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return str(category.id)


async def _create_difficulty_level(
    name: str = "超簡単", description: str = "誰でも分かる問題。"
) -> int:
    async with AsyncSessionLocal() as session:
        difficulty_level = DifficultyLevel(name=name, description=description)
        session.add(difficulty_level)
        await session.commit()
        await session.refresh(difficulty_level)
        return difficulty_level.id


async def _promote_to_admin(email: str) -> None:
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        credential = (
            await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))
        ).scalar_one()
        credential.role = UserRole.ADMIN
        await session.commit()


async def test_generate_list_answer_and_admin_manage_quiz(client: AsyncClient, monkeypatch) -> None:
    _mock_quiz_generation(monkeypatch)
    category_id = await _create_category()
    difficulty_level_id = await _create_difficulty_level()

    token = await _register_and_login(client, "quizmaker@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    generate_response = await client.post(
        "/api/v1/quizzes/generate",
        json={
            "category_id": category_id,
            "difficulty_level_id": difficulty_level_id,
            "keywords": ["日本", "首都"],
        },
        headers=headers,
    )
    assert generate_response.status_code == 201
    quiz = generate_response.json()
    assert quiz["title"] == "日本の首都"
    assert len(quiz["options"]) == 4
    assert quiz["difficulty_level"]["id"] == difficulty_level_id
    quiz_id = quiz["id"]
    correct_option_id = next(o["id"] for o in quiz["options"] if o["is_correct"])

    list_response = await client.get("/api/v1/quizzes", params={"category_id": category_id})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = await client.get(f"/api/v1/quizzes/{quiz_id}")
    assert get_response.status_code == 200
    assert get_response.json()["my_attempt"] is None

    attempt_response = await client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        json={"selected_option_id": correct_option_id, "favorite": True},
        headers=headers,
    )
    assert attempt_response.status_code == 200
    assert attempt_response.json()["is_correct"] is True

    summary_response = await client.get("/api/v1/users/me/summary", headers=headers)
    assert summary_response.json() == {"challenged_count": 1, "corrected_count": 1}

    favorite_list_response = await client.get(
        "/api/v1/quizzes", params={"favorite": True}, headers=headers
    )
    assert favorite_list_response.json()["total"] == 1

    update_payload = {
        "title": "改題",
        "question": "改訂後の問題文",
        "commentary": "改訂後の解説",
        "options": [
            {"content": "A", "is_correct": True},
            {"content": "B", "is_correct": False},
        ],
    }

    forbidden_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=update_payload, headers=headers
    )
    assert forbidden_response.status_code == 403

    await _promote_to_admin("quizmaker@example.com")

    update_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=update_payload, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "改題"

    delete_response = await client.delete(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    assert delete_response.status_code == 204


async def test_quiz_list_requires_auth_for_favorite_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/quizzes", params={"favorite": True})

    assert response.status_code == 401


async def test_generate_quiz_returns_404_for_unknown_category(
    client: AsyncClient, monkeypatch
) -> None:
    _mock_quiz_generation(monkeypatch)
    difficulty_level_id = await _create_difficulty_level()
    token = await _register_and_login(client, "nocategory@example.com")

    response = await client.post(
        "/api/v1/quizzes/generate",
        json={
            "category_id": "00000000-0000-0000-0000-000000000000",
            "difficulty_level_id": difficulty_level_id,
            "keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_submit_attempt_with_unknown_option_returns_400(
    client: AsyncClient, monkeypatch
) -> None:
    _mock_quiz_generation(monkeypatch)
    category_id = await _create_category("歴史")
    difficulty_level_id = await _create_difficulty_level()
    token = await _register_and_login(client, "badoption@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    generate_response = await client.post(
        "/api/v1/quizzes/generate",
        json={
            "category_id": category_id,
            "difficulty_level_id": difficulty_level_id,
            "keywords": [],
        },
        headers=headers,
    )
    quiz_id = generate_response.json()["id"]

    response = await client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        json={"selected_option_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )

    assert response.status_code == 400


async def test_generate_quiz_returns_502_when_generation_keeps_failing(
    client: AsyncClient, monkeypatch
) -> None:
    invalid_answer = _valid_answer()
    invalid_answer.options = invalid_answer.options[:3]
    _mock_quiz_generation(monkeypatch, answers=itertools.repeat(invalid_answer))
    category_id = await _create_category("科学")
    difficulty_level_id = await _create_difficulty_level()
    token = await _register_and_login(client, "alwaysfails@example.com")

    response = await client.post(
        "/api/v1/quizzes/generate",
        json={
            "category_id": category_id,
            "difficulty_level_id": difficulty_level_id,
            "keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 502


async def test_generate_quiz_returns_429_after_hourly_rate_limit(
    client: AsyncClient, monkeypatch
) -> None:
    category_id = await _create_category("レート制限")
    difficulty_level_id = await _create_difficulty_level()
    token = await _register_and_login(client, "ratelimited@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(5):
        _mock_quiz_generation(monkeypatch)
        response = await client.post(
            "/api/v1/quizzes/generate",
            json={
                "category_id": category_id,
                "difficulty_level_id": difficulty_level_id,
                "keywords": [],
            },
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.post(
        "/api/v1/quizzes/generate",
        json={
            "category_id": category_id,
            "difficulty_level_id": difficulty_level_id,
            "keywords": [],
        },
        headers=headers,
    )

    assert response.status_code == 429
    assert (
        response.json()["detail"]
        == "規定のリクエスト回数に達しました。制限解除までしばらくお待ちください。"
    )
