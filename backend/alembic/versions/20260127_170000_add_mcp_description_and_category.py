"""add_mcp_description_and_category

Revision ID: b9c4d5e6f8g9
Revises: a8b3c4d5e6f7
Create Date: 2026-01-27 17:00:00.000000

添加 MCP 服务器的 description 和 category 字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c4d5e6f8g9"
down_revision: str | None = "a8b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 description 和 category 字段"""

    # 检查表是否存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "mcp_servers" in tables:
        # 获取现有列
        columns = [col["name"] for col in inspector.get_columns("mcp_servers")]

        if "description" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "description",
                    sa.Text(),
                    nullable=True,
                    comment="服务器描述",
                ),
            )

        if "category" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "category",
                    sa.String(50),
                    nullable=True,
                    comment="分类",
                ),
            )


def downgrade() -> None:
    """移除 description 和 category 字段"""
    op.drop_column("mcp_servers", "category")
    op.drop_column("mcp_servers", "description")
