"""seed categories and admin user

Revision ID: 72c54fa6fa45
Revises: 1a27883aca26
Create Date: 2026-08-25 12:03:36.533421

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import column, table

from app.core.security import hash_password

# revision identifiers, used by Alembic.
revision: str = "72c54fa6fa45"
down_revision: str | Sequence[str] | None = "1a27883aca26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# scripts/seed.pyのCATEGORY_NAMESと揃え、ローカル/dev環境がseed.pyで作るデータと
# 本番の初期状態を一致させる。
CATEGORY_NAMES = [
    "アニメ・ゲーム",
    "美術",
    "観光",
    "スポーツ",
    "政治・経済",
    "音楽",
    "映画",
    "グルメ",
]

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin0123"
ADMIN_DISPLAY_NAME = "ADMIN_USER"

categories_table = table(
    "categories", column("id", sa.Uuid(as_uuid=True)), column("name", sa.String)
)
users_table = table(
    "users",
    column("id", sa.Uuid(as_uuid=True)),
    column("display_name", sa.String),
    column("is_active", sa.Boolean),
)
authentications_table = table(
    "authentications",
    column("id", sa.Uuid(as_uuid=True)),
    column("user_id", sa.Uuid(as_uuid=True)),
    column("email", sa.String),
    column("hashed_password", sa.String),
    column("role", sa.Enum("USER", "ADMIN", name="user_role")),
)


def upgrade() -> None:
    conn = op.get_bind()

    # categories.nameはUNIQUE制約があるため、scripts/seed.pyを既に実行済みの環境
    # (開発者のローカルDB等)で本マイグレーションを適用しても重複エラーにならないよう
    # ON CONFLICT DO NOTHINGにする。
    category_rows = [{"id": uuid.uuid4(), "name": name} for name in CATEGORY_NAMES]
    conn.execute(
        pg_insert(categories_table)
        .values(category_rows)
        .on_conflict_do_nothing(index_elements=["name"])
    )

    # authentications.emailもUNIQUE制約があるため、
    # 既に同じ管理者ユーザーが存在する場合は何もしない。
    existing_admin = conn.execute(
        sa.text("SELECT 1 FROM authentications WHERE email = :email"), {"email": ADMIN_EMAIL}
    ).first()
    if existing_admin is None:
        admin_user_id = uuid.uuid4()
        conn.execute(
            users_table.insert().values(
                id=admin_user_id, display_name=ADMIN_DISPLAY_NAME, is_active=True
            )
        )
        conn.execute(
            authentications_table.insert().values(
                id=uuid.uuid4(),
                user_id=admin_user_id,
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role="ADMIN",
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("DELETE FROM authentications WHERE email = :email"), {"email": ADMIN_EMAIL}
    )
    conn.execute(
        sa.text(
            "DELETE FROM users WHERE id NOT IN (SELECT user_id FROM authentications) "
            "AND display_name = :display_name"
        ),
        {"display_name": ADMIN_DISPLAY_NAME},
    )

    conn.execute(
        sa.text(
            "DELETE FROM categories WHERE name = ANY(:names) "
            "AND id NOT IN (SELECT category_id FROM quizzes)"
        ),
        {"names": CATEGORY_NAMES},
    )
