"""user display_name rename and email move to authentications

Revision ID: 8c23c16484f0
Revises: 678b95a6c81d
Create Date: 2026-08-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c23c16484f0"
down_revision: str | Sequence[str] | None = "678b95a6c81d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "full_name", new_column_name="display_name")

    # emailは「ユーザーのプロフィール」ではなく「認証情報」の一部としてauthenticationsへ移動する。
    op.add_column("authentications", sa.Column("email", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE authentications SET email = users.email "
        "FROM users WHERE authentications.user_id = users.id"
    )
    op.alter_column("authentications", "email", nullable=False)
    op.create_index("ix_authentications_email", "authentications", ["email"], unique=True)

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")


def downgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE users SET email = authentications.email "
        "FROM authentications WHERE authentications.user_id = users.id"
    )
    op.alter_column("users", "email", nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.drop_index("ix_authentications_email", table_name="authentications")
    op.drop_column("authentications", "email")

    op.alter_column("users", "display_name", new_column_name="full_name")
