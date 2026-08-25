from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category, DifficultyLevel, Keyword
from app.repositories.keyword import KeywordRepository
from app.repositories.quiz import QuizRepository
from app.services.category import CategoryService
from app.services.keyword import KeywordService
from app.services.user import UserService
from tests.conftest import FakeRedis


async def _create_difficulty_level(session: AsyncSession, level: int = 1) -> DifficultyLevel:
    difficulty_level = DifficultyLevel(name="簡単", description="説明", level=level)
    session.add(difficulty_level)
    await session.commit()
    return difficulty_level


async def _create_user(session: AsyncSession, display_name: str):
    return await UserService(session).create_user(display_name=display_name, password="s3cret")


async def _create_quiz(
    session: AsyncSession,
    *,
    category: Category,
    difficulty_level: DifficultyLevel,
    user,
    keywords: list[Keyword] | None = None,
):
    quiz = await QuizRepository(session).create(
        title="タイトル",
        question="問題文",
        commentary="解説",
        category_id=category.id,
        created_by_id=user.id,
        difficulty_level_id=difficulty_level.id,
        options=[("A", True), ("B", False), ("C", False), ("D", False)],
        keywords=keywords or [],
    )
    await session.commit()
    return quiz


async def test_list_categories_returns_sorted_by_name(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> None:
    db_session.add_all([Category(name="歴史"), Category(name="地理")])
    await db_session.commit()

    categories = await CategoryService(db_session, fake_redis).list_categories()

    assert [c.name for c in categories] == ["地理", "歴史"]


async def test_keyword_get_or_create_is_idempotent(db_session: AsyncSession) -> None:
    repo = KeywordRepository(db_session)
    first = await repo.get_or_create("日本")
    second = await repo.get_or_create("日本")

    assert first.id == second.id


async def test_list_keywords_returns_created_keywords(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> None:
    repo = KeywordRepository(db_session)
    await repo.get_or_create("歴史")
    await repo.get_or_create("地理")
    await db_session.commit()

    keywords = await KeywordService(db_session, fake_redis).list_keywords()

    assert {k.keyword for k in keywords} == {"歴史", "地理"}


async def test_keyword_ranking_orders_by_quiz_count_desc_then_name_asc(
    db_session: AsyncSession, fake_redis: FakeRedis,
) -> None:
    difficulty_level = await _create_difficulty_level(db_session)
    category = Category(name="地理")
    db_session.add(category)
    await db_session.commit()
    user = await _create_user(db_session, display_name="keyword-ranker")

    keyword_repo = KeywordRepository(db_session)
    popular = await keyword_repo.get_or_create("人気")
    tie_a = await keyword_repo.get_or_create("あ行")
    tie_b = await keyword_repo.get_or_create("か行")
    await keyword_repo.get_or_create("未使用")  # 紐づくクイズなし
    await db_session.commit()

    for keyword in (popular, popular, tie_a, tie_b):
        await _create_quiz(
            db_session,
            category=category,
            difficulty_level=difficulty_level,
            user=user,
            keywords=[keyword],
        )

    ranking = await KeywordService(db_session, fake_redis).list_ranking()

    assert [(r.keyword, r.quiz_count) for r in ranking] == [
        ("人気", 2),
        ("あ行", 1),
        ("か行", 1),
        ("未使用", 0),
    ]


async def test_keyword_ranking_limit_returns_top_n(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> None:
    difficulty_level = await _create_difficulty_level(db_session)
    category = Category(name="地理")
    db_session.add(category)
    await db_session.commit()
    user = await _create_user(db_session, display_name="keyword-ranker-limit")

    keyword_repo = KeywordRepository(db_session)
    popular = await keyword_repo.get_or_create("人気")
    tie_a = await keyword_repo.get_or_create("あ行")
    await keyword_repo.get_or_create("か行")
    await db_session.commit()

    for keyword in (popular, popular, tie_a):
        await _create_quiz(
            db_session,
            category=category,
            difficulty_level=difficulty_level,
            user=user,
            keywords=[keyword],
        )

    ranking = await KeywordService(db_session, fake_redis).list_ranking(limit=2)

    assert [r.keyword for r in ranking] == ["人気", "あ行"]


async def test_category_ranking_orders_by_quiz_count_desc_then_name_asc(
    db_session: AsyncSession, fake_redis: FakeRedis,
) -> None:
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session, display_name="category-ranker")

    popular = Category(name="人気カテゴリ")
    tie_a = Category(name="あ行カテゴリ")
    tie_b = Category(name="か行カテゴリ")
    db_session.add_all([popular, tie_a, tie_b, Category(name="未使用カテゴリ")])
    await db_session.commit()

    for category in (popular, popular, tie_a, tie_b):
        await _create_quiz(
            db_session, category=category, difficulty_level=difficulty_level, user=user
        )

    ranking = await CategoryService(db_session, fake_redis).list_ranking()

    assert [(r.name, r.quiz_count) for r in ranking] == [
        ("人気カテゴリ", 2),
        ("あ行カテゴリ", 1),
        ("か行カテゴリ", 1),
        ("未使用カテゴリ", 0),
    ]


async def test_category_ranking_limit_returns_top_n(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> None:
    difficulty_level = await _create_difficulty_level(db_session)
    user = await _create_user(db_session, display_name="category-ranker-limit")

    popular = Category(name="人気カテゴリ")
    tie_a = Category(name="あ行カテゴリ")
    db_session.add_all([popular, tie_a, Category(name="か行カテゴリ")])
    await db_session.commit()

    for category in (popular, popular, tie_a):
        await _create_quiz(
            db_session, category=category, difficulty_level=difficulty_level, user=user
        )

    ranking = await CategoryService(db_session, fake_redis).list_ranking(limit=2)

    assert [r.name for r in ranking] == ["人気カテゴリ", "あ行カテゴリ"]
