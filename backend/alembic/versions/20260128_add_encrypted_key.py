"""add encrypted_key to api_keys

Revision ID: d2e3f4g5h6i7
Create Date: 2026-01-28

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = 'd2e3f4g5h6i7'
down_revision: str | None = 'c1d2e3f4g5h6'  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 第一步：添加可空列
    op.add_column('api_keys', sa.Column('encrypted_key', sa.String(length=512), nullable=True))

    # 第二步：为现有数据设置默认值（占位符）
    op.execute("UPDATE api_keys SET encrypted_key = 'legacy_key' WHERE encrypted_key IS NULL")

    # 第三步：设置为 NOT NULL
    op.alter_column('api_keys', 'encrypted_key', nullable=False)


def downgrade() -> None:
    op.drop_column('api_keys', 'encrypted_key')
