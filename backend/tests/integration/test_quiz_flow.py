import itertools
import uuid
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.graph import nodes
from app.core.database import AsyncSessionLocal
from app.models.quiz import Category, DifficultyLevel
from app.models.user import UserCredential, UserRole
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
        json={"email": email, "password": "s3cret-pass", "display_name": "Tester"},
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
    name: str = "超簡単", description: str = "誰でも分かる問題。", level: int = 1
) -> str:
    async with AsyncSessionLocal() as session:
        difficulty_level = DifficultyLevel(name=name, description=description, level=level)
        session.add(difficulty_level)
        await session.commit()
        await session.refresh(difficulty_level)
        return str(difficulty_level.id)


async def _promote_to_admin(email: str) -> None:
    async with AsyncSessionLocal() as session:
        credential = (
            await session.execute(select(UserCredential).where(UserCredential.email == email))
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
    assert "my_attempt" not in quiz
    assert "category" not in quiz
    assert "keywords" not in quiz
    assert "created_at" not in quiz
    assert "updated_at" not in quiz
    quiz_id = quiz["id"]

    list_response = await client.get("/api/v1/quizzes", params={"category_id": category_id})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = await client.get(f"/api/v1/quizzes/{quiz_id}")
    assert get_response.status_code == 200
    assert get_response.json()["my_attempt"] is None

    attempt_response = await client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        json={"corrected": True, "favorite": True},
        headers=headers,
    )
    assert attempt_response.status_code == 200
    assert attempt_response.json()["corrected"] is True

    summary_response = await client.get("/api/v1/users/profile/summary", headers=headers)
    assert summary_response.json() == {"challenged_count": 1, "corrected_count": 1}

    favorite_list_response = await client.get(
        "/api/v1/quizzes", params={"favorite": True}, headers=headers
    )
    assert favorite_list_response.json()["total"] == 1

    mine_list_response = await client.get("/api/v1/quizzes", params={"mine": True}, headers=headers)
    assert mine_list_response.json()["total"] == 1
    assert mine_list_response.json()["items"][0]["id"] == quiz_id

    sorted_list_response = await client.get("/api/v1/quizzes", params={"sort_by": "updated_at"})
    assert sorted_list_response.status_code == 200

    original_options = get_response.json()["options"]
    original_option_ids = [option["id"] for option in original_options]
    assert len(original_option_ids) == 4

    mismatched_id_payload = {
        "options": [
            {"id": str(uuid.uuid4()), "content": "A", "is_correct": True},
            {"id": original_option_ids[1], "content": "B", "is_correct": False},
            {"id": original_option_ids[2], "content": "C", "is_correct": False},
            {"id": original_option_ids[3], "content": "D", "is_correct": False},
        ],
    }
    mismatched_id_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=mismatched_id_payload, headers=headers
    )
    assert mismatched_id_response.status_code == 400

    valid_id_payload = {
        "options": [
            {"id": original_option_ids[0], "content": "東京", "is_correct": True},
            {"id": original_option_ids[1], "content": "大阪", "is_correct": False},
            {"id": original_option_ids[2], "content": "京都", "is_correct": False},
            {"id": original_option_ids[3], "content": "札幌", "is_correct": False},
        ],
    }
    valid_id_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=valid_id_payload, headers=headers
    )
    assert valid_id_response.status_code == 204

    get_after_valid_update_response = await client.get(f"/api/v1/quizzes/{quiz_id}")
    assert len(get_after_valid_update_response.json()["options"]) == 4
    assert get_after_valid_update_response.json()["options"][0]["content"] == "東京"

    update_payload = {
        "options": [
            {"content": "A", "is_correct": True},
            {"content": "B", "is_correct": False},
        ],
    }

    outsider_token = await _register_and_login(client, "outsider@example.com")
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    forbidden_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=update_payload, headers=outsider_headers
    )
    assert forbidden_response.status_code == 403

    update_response = await client.patch(
        f"/api/v1/quizzes/{quiz_id}", json=update_payload, headers=headers
    )
    assert update_response.status_code == 204
    assert update_response.content == b""

    verify_response = await client.get(f"/api/v1/quizzes/{quiz_id}")
    assert verify_response.json()["title"] == "日本の首都"  # 本文は編集対象外のため変化しない
    assert len(verify_response.json()["options"]) == 2

    delete_forbidden_response = await client.delete(
        f"/api/v1/quizzes/{quiz_id}", headers=outsider_headers
    )
    assert delete_forbidden_response.status_code == 403

    await _promote_to_admin("outsider@example.com")

    delete_response = await client.delete(f"/api/v1/quizzes/{quiz_id}", headers=outsider_headers)
    assert delete_response.status_code == 204


async def test_quiz_list_requires_auth_for_favorite_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/quizzes", params={"favorite": True})

    assert response.status_code == 401


async def test_quiz_list_requires_auth_for_mine_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/quizzes", params={"mine": True})

    assert response.status_code == 401


async def test_quiz_list_requires_auth_for_corrected_false_filter(client: AsyncClient) -> None:
    """corrected=falseは明示的な絞り込み指定であり、未指定(フィルタなし)とは区別して認証必須にする。"""
    response = await client.get("/api/v1/quizzes", params={"corrected": False})

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
