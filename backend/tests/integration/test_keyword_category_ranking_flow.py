import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.quiz import Category, DifficultyLevel, Keyword
from app.models.user import User, UserCredential
from app.repositories.quiz import QuizRepository

pytestmark = pytest.mark.integration


async def _create_category(name: str) -> Category:
    async with AsyncSessionLocal() as session:
        category = Category(name=name)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category


async def _create_difficulty_level(level: int = 1) -> DifficultyLevel:
    async with AsyncSessionLocal() as session:
        difficulty_level = DifficultyLevel(name="簡単", description="説明", level=level)
        session.add(difficulty_level)
        await session.commit()
        await session.refresh(difficulty_level)
        return difficulty_level


async def _create_keyword(text: str) -> Keyword:
    async with AsyncSessionLocal() as session:
        keyword = Keyword(keyword=text)
        session.add(keyword)
        await session.commit()
        await session.refresh(keyword)
        return keyword


async def _get_user_id(display_name: str):
    async with AsyncSessionLocal() as session:
        credential = (
            await session.execute(
                select(UserCredential)
                .join(User, User.id == UserCredential.user_id)
                .where(User.display_name == display_name)
            )
        ).scalar_one()
        return credential.user_id


async def _create_quiz(*, category: Category, difficulty_level: DifficultyLevel, user_id, keywords):
    async with AsyncSessionLocal() as session:
        await QuizRepository(session).create(
            title="タイトル",
            question="問題文",
            commentary="解説",
            category_id=category.id,
            created_by_id=user_id,
            difficulty_level_id=difficulty_level.id,
            options=[("A", True), ("B", False), ("C", False), ("D", False)],
            keywords=keywords,
        )
        await session.commit()


async def test_keyword_and_category_ranking_orders_by_quiz_count(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"display_name": "ranking-tester", "password": "s3cret-pass"},
    )
    user_id = await _get_user_id("ranking-tester")
    difficulty_level = await _create_difficulty_level()

    popular_category = await _create_category("人気カテゴリ")
    tie_a_category = await _create_category("あ行カテゴリ")
    tie_b_category = await _create_category("か行カテゴリ")
    await _create_category("未使用カテゴリ")

    popular_keyword = await _create_keyword("人気")
    tie_a_keyword = await _create_keyword("あ行")
    tie_b_keyword = await _create_keyword("か行")
    await _create_keyword("未使用")

    await _create_quiz(
        category=popular_category,
        difficulty_level=difficulty_level,
        user_id=user_id,
        keywords=[popular_keyword],
    )
    await _create_quiz(
        category=popular_category,
        difficulty_level=difficulty_level,
        user_id=user_id,
        keywords=[popular_keyword],
    )
    await _create_quiz(
        category=tie_a_category,
        difficulty_level=difficulty_level,
        user_id=user_id,
        keywords=[tie_a_keyword],
    )
    await _create_quiz(
        category=tie_b_category,
        difficulty_level=difficulty_level,
        user_id=user_id,
        keywords=[tie_b_keyword],
    )

    keyword_response = await client.get("/api/v1/keywords/ranking")
    assert keyword_response.status_code == 200
    assert [(item["keyword"], item["quiz_count"]) for item in keyword_response.json()] == [
        ("人気", 2),
        ("あ行", 1),
        ("か行", 1),
        ("未使用", 0),
    ]

    category_response = await client.get("/api/v1/categories/ranking")
    assert category_response.status_code == 200
    assert [(item["name"], item["quiz_count"]) for item in category_response.json()] == [
        ("人気カテゴリ", 2),
        ("あ行カテゴリ", 1),
        ("か行カテゴリ", 1),
        ("未使用カテゴリ", 0),
    ]

    limited_response = await client.get("/api/v1/keywords/ranking", params={"limit": 2})
    assert [item["keyword"] for item in limited_response.json()] == ["人気", "あ行"]

    # 既存の一覧エンドポイントはquiz_countを含まない従来通りの形のまま
    plain_keywords_response = await client.get("/api/v1/keywords")
    assert "quiz_count" not in plain_keywords_response.json()[0]
