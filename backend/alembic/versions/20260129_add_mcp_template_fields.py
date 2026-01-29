"""add_mcp_template_fields

Revision ID: h6i7j8k9l0m1
Revises: g5h6i7j8k9l0
Create Date: 2026-01-29

为 mcp_servers 表添加 template_id 和 inherit_defaults 字段
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h6i7j8k9l0m1"
down_revision: str | None = "g5h6i7j8k9l0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 template_id 和 inherit_defaults 字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "mcp_servers" in tables:
        columns = [col["name"] for col in inspector.get_columns("mcp_servers")]

        if "template_id" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "template_id",
                    sa.String(50),
                    nullable=True,
                    comment="来源模板ID，如 'github', 'postgres'",
                ),
            )
            op.create_index(
                "ix_mcp_servers_template_id",
                "mcp_servers",
                ["template_id"],
                unique=False,
            )

        if "inherit_defaults" not in columns:
            op.add_column(
                "mcp_servers",
                sa.Column(
                    "inherit_defaults",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                    comment="是否继承模板默认配置（可选同步）",
                ),
            )


def downgrade() -> None:
    """移除 template_id 和 inherit_defaults 字段"""
    op.drop_index("ix_mcp_servers_template_id", table_name="mcp_servers")
    op.drop_column("mcp_servers", "inherit_defaults")
    op.drop_column("mcp_servers", "template_id")
