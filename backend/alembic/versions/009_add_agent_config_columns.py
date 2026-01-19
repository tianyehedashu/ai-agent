"""add agent config columns

Revision ID: 009_add_agent_config_columns
Revises: 008_add_langgraph_tables
Create Date: 2026-01-17

添加 Agent 配置相关的列：temperature, max_tokens, max_iterations, is_public
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_add_agent_config_columns"
down_revision: str | None = "008_add_langgraph_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 添加 temperature 列
    op.add_column(
        "agents",
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
    )

    # 添加 max_tokens 列
    op.add_column(
        "agents",
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="4096"),
    )

    # 添加 max_iterations 列
    op.add_column(
        "agents",
        sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="20"),
    )

    # 添加 is_public 列（如果不存在）
    # 检查是否已存在 is_active，如果存在则重命名
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'agents' AND column_name = 'is_public'"
        )
    )
    if not result.fetchone():
        # 检查是否有 is_active 列
        result = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'agents' AND column_name = 'is_active'"
            )
        )
        if result.fetchone():
            # 重命名 is_active 为 is_public
            op.alter_column("agents", "is_active", new_column_name="is_public")
        else:
            # 添加新列
            op.add_column(
                "agents",
                sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
            )

    # 移除 server_default（可选，让应用层管理默认值）
    op.alter_column("agents", "temperature", server_default=None)
    op.alter_column("agents", "max_tokens", server_default=None)
    op.alter_column("agents", "max_iterations", server_default=None)


def downgrade() -> None:
    # 删除添加的列
    op.drop_column("agents", "temperature")
    op.drop_column("agents", "max_tokens")
    op.drop_column("agents", "max_iterations")

    # 将 is_public 改回 is_active
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'agents' AND column_name = 'is_public'"
        )
    )
    if result.fetchone():
        op.alter_column("agents", "is_public", new_column_name="is_active")
