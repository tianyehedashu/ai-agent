"""add_mcp_dynamic_prompts

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-01-29

MCP 动态 Prompts 表：按 server 存储可运行时添加的 prompt 模板（客户端直连 MCP 等）
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "q9r0s1t2u3v4"
down_revision: str | None = "p8q9r0s1t2u3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_dynamic_prompts",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "server_kind", sa.String(30), nullable=False, comment="streamable_http | db_server"
        ),
        sa.Column(
            "server_id", sa.String(100), nullable=False, comment="server_name or server UUID"
        ),
        sa.Column("prompt_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "arguments_schema",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment='[{"name":"x","description":"...","required":true}]',
        ),
        sa.Column("template", sa.Text(), nullable=False),
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
        "ix_mcp_dynamic_prompts_server", "mcp_dynamic_prompts", ["server_kind", "server_id"]
    )
    op.create_unique_constraint(
        "uq_mcp_dynamic_prompts_server_prompt",
        "mcp_dynamic_prompts",
        ["server_kind", "server_id", "prompt_key"],
    )


def downgrade() -> None:
    op.drop_table("mcp_dynamic_prompts")
