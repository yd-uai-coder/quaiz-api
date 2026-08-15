"""add difficulty levels

Revision ID: 943c6a5db794
Revises: 2b97c8ec8533
Create Date: 2026-08-15 01:52:10.396818

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "943c6a5db794"
down_revision: str | Sequence[str] | None = "2b97c8ec8533"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIFFICULTY_LEVELS = [
    {
        "id": 1,
        "name": "超簡単",
        "description": "知っていて当たり前。ひっかけも一切なしのストレートな問題。",
    },
    {
        "id": 2,
        "name": "一般常識・義務教育レベル",
        "description": (
            "中学生以上の普通の大人なら、8〜9割は答えられる。"
            "学校で絶対に習ったことや、ニュースで日常的に見る言葉。"
        ),
    },
    {
        "id": 3,
        "name": "ちょっとした教養・大人の雑学レベル",
        "description": (
            "ニュースや本をよく見る「物知りな人」なら、答えられる。一般的なクイズ番組のメインゾーン。"
        ),
    },
    {
        "id": 4,
        "name": "クイズマニアレベル",
        "description": (
            "その分野のオタクや、普段からクイズが好きな人。"
            "教科書の隅に載っている知識や、少し「ひねり」のある問題。"
        ),
    },
    {
        "id": 5,
        "name": "専門家レベル",
        "description": (
            "競技クイズプレイヤー、大学の教授、または狂気的なオタク。一般人は問題文の意味すら分からない。"
        ),
    },
]

difficulty_levels_table = table(
    "difficulty_levels",
    column("id", sa.Integer),
    column("name", sa.String),
    column("description", sa.String),
)


def upgrade() -> None:
    op.create_table(
        "difficulty_levels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(difficulty_levels_table, DIFFICULTY_LEVELS)
    # PostgreSQLのSERIALはINSERTでid明示指定してもシーケンスが追従しないため、次回のINSERTに備えて進める。
    op.execute(
        "SELECT setval(pg_get_serial_sequence('difficulty_levels', 'id'), "
        "(SELECT MAX(id) FROM difficulty_levels))"
    )

    # NOT NULL制約を課す前に、既存クイズへランダムな難易度(1〜5)を割り当てる。
    op.add_column("quizzes", sa.Column("difficulty_level_id", sa.Integer(), nullable=True))
    op.execute("UPDATE quizzes SET difficulty_level_id = (floor(random() * 5) + 1)::int")
    op.alter_column("quizzes", "difficulty_level_id", nullable=False)
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
    op.drop_constraint(
        "fk_quizzes_difficulty_level_id_difficulty_levels", "quizzes", type_="foreignkey"
    )
    op.drop_index("ix_quizzes_difficulty_level_id", table_name="quizzes")
    op.drop_column("quizzes", "difficulty_level_id")
    op.drop_table("difficulty_levels")
