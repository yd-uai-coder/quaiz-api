from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import DifficultyLevel
from app.services.difficulty_level import DifficultyLevelService


async def test_list_difficulty_levels_returns_sorted_by_id(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            DifficultyLevel(name="専門家レベル", description="狂気的なオタク向け。"),
            DifficultyLevel(name="超簡単", description="誰でも分かる問題。"),
        ]
    )
    await db_session.commit()

    levels = await DifficultyLevelService(db_session).list_difficulty_levels()

    assert [level.name for level in levels] == ["専門家レベル", "超簡単"]
    assert levels[0].id < levels[1].id
