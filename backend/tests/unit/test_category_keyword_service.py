from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Category
from app.repositories.keyword import KeywordRepository
from app.services.category import CategoryService
from app.services.keyword import KeywordService


async def test_list_categories_returns_sorted_by_name(db_session: AsyncSession) -> None:
    db_session.add_all([Category(name="歴史"), Category(name="地理")])
    await db_session.commit()

    categories = await CategoryService(db_session).list_categories()

    assert [c.name for c in categories] == ["地理", "歴史"]


async def test_keyword_get_or_create_is_idempotent(db_session: AsyncSession) -> None:
    repo = KeywordRepository(db_session)
    first = await repo.get_or_create("日本")
    second = await repo.get_or_create("日本")

    assert first.id == second.id


async def test_list_keywords_returns_created_keywords(db_session: AsyncSession) -> None:
    repo = KeywordRepository(db_session)
    await repo.get_or_create("歴史")
    await repo.get_or_create("地理")
    await db_session.commit()

    keywords = await KeywordService(db_session).list_keywords()

    assert {k.keyword for k in keywords} == {"歴史", "地理"}
