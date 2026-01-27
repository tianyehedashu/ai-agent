"""add_config_column_to_sessions

Revision ID: 5783302b5009
Revises: 011
Create Date: 2026-01-23 21:27:03.079594

添加 config 列到 sessions 表（JSONB 类型，默认值为空字典）
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5783302b5009"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 config 列到 sessions 表"""
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("sessions")]

    if "config" not in columns:
        op.add_column(
            "sessions",
            sa.Column(
                "config",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    """移除 config 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("sessions")]

    if "config" in columns:
        op.drop_column("sessions", "config")
