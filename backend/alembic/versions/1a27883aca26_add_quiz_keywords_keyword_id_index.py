"""add_quiz_keywords_keyword_id_index

Revision ID: 1a27883aca26
Revises: 8c23c16484f0
Create Date: 2026-08-23 14:53:36.558467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a27883aca26'
down_revision: Union[str, Sequence[str], None] = '8c23c16484f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # quiz_keywordsの複合PK(quiz_id, keyword_id)の後方列だけではkeyword_id単体の
    # GROUP BY(キーワード人気ランキング集計)に使えないため、単独索引を追加する。
    op.create_index('ix_quiz_keywords_keyword_id', 'quiz_keywords', ['keyword_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_quiz_keywords_keyword_id', table_name='quiz_keywords')
