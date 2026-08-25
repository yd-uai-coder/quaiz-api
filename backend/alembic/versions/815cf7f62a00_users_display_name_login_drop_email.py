"""users display name login drop email

適用前に本番DBで
`SELECT display_name, count(*) FROM users GROUP BY display_name HAVING count(*) > 1`
を実行し、重複が無いことを確認すること(重複があるとunique index作成で失敗する)。

Revision ID: 815cf7f62a00
Revises: 72c54fa6fa45
Create Date: 2026-08-25 15:52:13.499578

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "815cf7f62a00"
down_revision: str | Sequence[str] | None = "72c54fa6fa45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 既存のNULL display_nameを補完する(現状のシードデータは全員display_name設定済みのため
    # 実質的に影響しない想定)。
    op.execute(
        "UPDATE users SET display_name = 'user_' || substr(id::text, 1, 8) "
        "WHERE display_name IS NULL"
    )
    op.alter_column("users", "display_name", existing_type=sa.String(length=255), nullable=False)
    op.create_index("ix_users_display_name", "users", ["display_name"], unique=True)

    op.drop_index("ix_authentications_email", table_name="authentications")
    op.drop_column("authentications", "email")


def downgrade() -> None:
    op.add_column("authentications", sa.Column("email", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE authentications SET email = "
        "'user_' || substr(user_id::text, 1, 8) || '@example.com'"
    )
    op.alter_column("authentications", "email", nullable=False)
    op.create_index("ix_authentications_email", "authentications", ["email"], unique=True)

    op.drop_index("ix_users_display_name", table_name="users")
    op.alter_column("users", "display_name", existing_type=sa.String(length=255), nullable=True)
