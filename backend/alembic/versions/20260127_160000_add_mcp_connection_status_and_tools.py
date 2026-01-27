"""add_mcp_connection_status_and_tools

Revision ID: a8b3c4d5e6f7
Revises: d3f606546828
Create Date: 2026-01-27 16:00:00.000000

添加 MCP 服务器连接状态和工具列表字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b3c4d5e6f7"
down_revision: str | None = "d3f606546828"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加连接状态和工具列表字段"""

    # 检查表是否存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "mcp_servers" in tables:
        # 获取现有列
        columns = [col["name"] for col in inspector.get_columns("mcp_servers")]

        # 添加新列（如果不存在）
        if "connection_status" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "connection_status",
                    sa.String(20),
                    nullable=True,
                    comment="连接状态: connected, failed, unknown",
                ),
            )

        if "last_connected_at" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "last_connected_at",
                    sa.String(50),
                    nullable=True,
                    comment="最后连接时间 (ISO格式)",
                ),
            )

        if "last_error" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "last_error", sa.Text(), nullable=True, comment="最后错误信息"
                ),
            )

        if "available_tools" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "available_tools",
                    JSONB,
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                    comment="可用工具列表",
                ),
            )


def downgrade() -> None:
    """移除连接状态和工具列表字段"""
    op.drop_column("mcp_servers", "available_tools")
    op.drop_column("mcp_servers", "last_error")
    op.drop_column("mcp_servers", "last_connected_at")
    op.drop_column("mcp_servers", "connection_status")
