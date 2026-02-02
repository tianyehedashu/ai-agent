"""add_mcp_dynamic_tools

Revision ID: p8q9r0s1t2u3
Revises: h6i7j8k9l0m1
Create Date: 2026-01-29

MCP 动态工具表：按 server 存储可运行时添加的工具（客户端直连 MCP 等）
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "p8q9r0s1t2u3"
down_revision: str | None = "h6i7j8k9l0m1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_dynamic_tools",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "server_kind", sa.String(30), nullable=False, comment="streamable_http | db_server"
        ),
        sa.Column(
            "server_id", sa.String(100), nullable=False, comment="server_name or server UUID"
        ),
        sa.Column("tool_key", sa.String(100), nullable=False),
        sa.Column("tool_type", sa.String(50), nullable=False),
        sa.Column("config_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_mcp_dynamic_tools_server", "mcp_dynamic_tools", ["server_kind", "server_id"]
    )
    op.create_unique_constraint(
        "uq_mcp_dynamic_tools_server_tool",
        "mcp_dynamic_tools",
        ["server_kind", "server_id", "tool_key"],
    )


def downgrade() -> None:
    op.drop_table("mcp_dynamic_tools")
