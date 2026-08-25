"""quizzes created by id nullable

ユーザー削除機能の追加に伴い、作成者が削除されたクイズはcreated_by_idをNULLにして
残す方式を採用する(DBレベルのON DELETE SET NULLで自動的にNULL化させる)。

Revision ID: 03fe3432fc02
Revises: 815cf7f62a00
Create Date: 2026-08-25 15:52:31.009157

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "03fe3432fc02"
down_revision: str | Sequence[str] | None = "815cf7f62a00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("quizzes", "created_by_id", nullable=True)
    op.drop_constraint("quizzes_created_by_id_fkey", "quizzes", type_="foreignkey")
    op.create_foreign_key(
        "quizzes_created_by_id_fkey",
        "quizzes",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # 既にcreated_by_idがNULLのクイズ(削除済みユーザーが作成した分)が存在する場合、
    # NOT NULLへの復帰は失敗する。ダウングレード前に該当行を手動で対処すること。
    op.drop_constraint("quizzes_created_by_id_fkey", "quizzes", type_="foreignkey")
    op.create_foreign_key(
        "quizzes_created_by_id_fkey", "quizzes", "users", ["created_by_id"], ["id"]
    )
    op.alter_column("quizzes", "created_by_id", nullable=False)
