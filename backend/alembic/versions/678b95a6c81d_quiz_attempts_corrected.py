"""quiz_attempts is_correct to corrected

Revision ID: 678b95a6c81d
Revises: 6861536c1d57
Create Date: 2026-08-18 01:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "678b95a6c81d"
down_revision: str | Sequence[str] | None = "6861536c1d57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # quiz_attempts.is_correctは「ユーザーの回答結果」の意味だが、名前が他の箇所(corrected_only等)と
    # 揃っていなかったため、用語をcorrectedに統一する。
    op.alter_column("quiz_attempts", "is_correct", new_column_name="corrected")


def downgrade() -> None:
    op.alter_column("quiz_attempts", "corrected", new_column_name="is_correct")
