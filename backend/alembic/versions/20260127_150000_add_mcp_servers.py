"""add_mcp_servers

Revision ID: d3f606546828
Revises: 5783302b5009
Create Date: 2026-01-27 15:00:00.000000

添加 MCP 服务器表（无外键约束）和默认系统级 MCP 服务器
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3f606546828'
down_revision: str | None = '5783302b5009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 MCP 服务器表并添加默认数据"""

    # 检查表是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "mcp_servers" not in tables:
        # 创建 mcp_servers 表（不使用外键）
        op.create_table(
            "mcp_servers",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                nullable=True,
                comment="所有者用户ID，NULL表示系统级服务器",
            ),
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("display_name", sa.String(200), nullable=True),
            sa.Column("url", sa.String(500), nullable=False),
            sa.Column("scope", sa.String(20), nullable=False, server_default="user"),
            sa.Column("env_type", sa.String(50), nullable=False),
            sa.Column("env_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Index("ix_mcp_servers_user_id", "user_id"),
            sa.Index("ix_mcp_servers_name", "name"),
        )

        # 添加默认系统级 MCP 服务器
        op.execute(
            """
            INSERT INTO mcp_servers (name, display_name, url, scope, env_type, env_config, enabled, description, category)
            VALUES
                ('filesystem', '文件系统', 'stdio://npx -y @modelcontextprotocol/server-filesystem', 'system', 'preinstalled', '{"allowedDirectories": ["."]}'::jsonb, true, '访问本地文件系统', 'productivity'),
                ('github', 'GitHub', 'stdio://npx -y @modelcontextprotocol/server-github', 'system', 'dynamic_injected', '{}'::jsonb, false, 'GitHub 仓库集成（需要配置 token）', 'development'),
                ('postgres', 'PostgreSQL', 'stdio://npx -y @modelcontextprotocol/server-postgres', 'system', 'dynamic_injected', '{"connectionString": ""}'::jsonb, false, 'PostgreSQL 数据库访问', 'database'),
                ('slack', 'Slack', 'stdio://npx -y @modelcontextprotocol/server-slack', 'system', 'dynamic_injected', '{}'::jsonb, false, 'Slack 集成（需要配置 token）', 'communication'),
                ('brave-search', 'Brave 搜索', 'stdio://npx -y @modelcontextprotocol/server-brave-search', 'system', 'preinstalled', '{}'::jsonb, true, 'Brave 网页搜索', 'search');
            """
        )


def downgrade() -> None:
    """删除 MCP 服务器表"""
    op.drop_table("mcp_servers")
