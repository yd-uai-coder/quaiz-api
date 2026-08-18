"""difficulty level uuid pk

Revision ID: 6861536c1d57
Revises: 943c6a5db794
Create Date: 2026-08-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6861536c1d57"
down_revision: str | Sequence[str] | None = "943c6a5db794"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # difficulty_levels: idが持っていた「難易度ランク」の意味をlevel列へ分離する。
    # 旧idはそのままランク値だったため、単純コピーでバックフィルできる。
    op.add_column("difficulty_levels", sa.Column("level", sa.Integer(), nullable=True))
    op.execute("UPDATE difficulty_levels SET level = id")
    op.alter_column("difficulty_levels", "level", nullable=False)
    op.create_unique_constraint("uq_difficulty_levels_level", "difficulty_levels", ["level"])

    # difficulty_levels: idをUUIDサロゲートキーに置き換える。
    op.add_column("difficulty_levels", sa.Column("new_id", sa.Uuid(as_uuid=True), nullable=True))
    op.execute("UPDATE difficulty_levels SET new_id = gen_random_uuid()")
    op.alter_column("difficulty_levels", "new_id", nullable=False)

    # quizzes: 旧int FKを新UUIDへ変換する(difficulty_levelsの旧id⇔new_idの対応で変換)。
    op.add_column(
        "quizzes", sa.Column("new_difficulty_level_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    op.execute(
        "UPDATE quizzes SET new_difficulty_level_id = difficulty_levels.new_id "
        "FROM difficulty_levels WHERE quizzes.difficulty_level_id = difficulty_levels.id"
    )
    op.alter_column("quizzes", "new_difficulty_level_id", nullable=False)

    # quizzes: 旧FK制約・旧インデックス・旧int列を撤去し、新UUID列をdifficulty_level_idへリネーム。
    op.drop_constraint(
        "fk_quizzes_difficulty_level_id_difficulty_levels", "quizzes", type_="foreignkey"
    )
    op.drop_index("ix_quizzes_difficulty_level_id", table_name="quizzes")
    op.drop_column("quizzes", "difficulty_level_id")
    op.alter_column("quizzes", "new_difficulty_level_id", new_column_name="difficulty_level_id")

    # difficulty_levels: 旧int PKを撤去し、新UUID列をidへリネームしてPKにする。
    op.drop_constraint("difficulty_levels_pkey", "difficulty_levels", type_="primary")
    op.drop_column("difficulty_levels", "id")
    op.alter_column("difficulty_levels", "new_id", new_column_name="id")
    op.create_primary_key("difficulty_levels_pkey", "difficulty_levels", ["id"])

    # quizzes: 新FK・新インデックスを同名で再構成する。
    op.create_index(
        "ix_quizzes_difficulty_level_id", "quizzes", ["difficulty_level_id"], unique=False
    )
    op.create_foreign_key(
        "fk_quizzes_difficulty_level_id_difficulty_levels",
        "quizzes",
        "difficulty_levels",
        ["difficulty_level_id"],
        ["id"],
    )


def downgrade() -> None:
    # quizzes/difficulty_levelsを旧int id構成に戻す。level列が旧idの値を保持しているため
    # 完全に復元できる。
    op.drop_constraint(
        "fk_quizzes_difficulty_level_id_difficulty_levels", "quizzes", type_="foreignkey"
    )
    op.drop_index("ix_quizzes_difficulty_level_id", table_name="quizzes")
    op.drop_constraint("difficulty_levels_pkey", "difficulty_levels", type_="primary")

    op.add_column("difficulty_levels", sa.Column("old_id", sa.Integer(), nullable=True))
    op.execute("UPDATE difficulty_levels SET old_id = level")
    op.alter_column("difficulty_levels", "old_id", nullable=False)

    op.add_column("quizzes", sa.Column("old_difficulty_level_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE quizzes SET old_difficulty_level_id = difficulty_levels.old_id "
        "FROM difficulty_levels WHERE quizzes.difficulty_level_id = difficulty_levels.id"
    )
    op.alter_column("quizzes", "old_difficulty_level_id", nullable=False)

    op.drop_column("quizzes", "difficulty_level_id")
    op.alter_column("quizzes", "old_difficulty_level_id", new_column_name="difficulty_level_id")

    op.drop_constraint("uq_difficulty_levels_level", "difficulty_levels", type_="unique")
    op.drop_column("difficulty_levels", "id")
    op.drop_column("difficulty_levels", "level")
    op.alter_column("difficulty_levels", "old_id", new_column_name="id")
    op.create_primary_key("difficulty_levels_pkey", "difficulty_levels", ["id"])
    op.alter_column(
        "difficulty_levels",
        "id",
        type_=sa.Integer(),
        autoincrement=True,
        existing_type=sa.Integer(),
    )

    op.create_index(
        "ix_quizzes_difficulty_level_id", "quizzes", ["difficulty_level_id"], unique=False
    )
    op.create_foreign_key(
        "fk_quizzes_difficulty_level_id_difficulty_levels",
        "quizzes",
        "difficulty_levels",
        ["difficulty_level_id"],
        ["id"],
    )
