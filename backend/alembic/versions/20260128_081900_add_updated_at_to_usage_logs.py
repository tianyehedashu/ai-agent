"""add_updated_at_to_usage_logs

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2026-01-28 08:19:00.000000

为 api_key_usage_logs 表添加 updated_at 列，保持架构一致性
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f4g5h6i7j8"
down_revision: str | None = "d2e3f4g5h6i7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 updated_at 列"""
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("api_key_usage_logs")]

    if "updated_at" not in columns:
        op.add_column(
            "api_key_usage_logs",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    """移除 updated_at 列"""
    op.drop_column("api_key_usage_logs", "updated_at")
