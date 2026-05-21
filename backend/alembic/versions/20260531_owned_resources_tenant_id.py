"""Owned 资源表迁 tenant_id；MCP 系统级拆表 system_mcp_servers

Revision ID: 20260531_ort
Revises: 20260530_dps_tenant
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260531_ort"
down_revision: str | None = "20260530_dps_tenant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERSONAL_TENANT_BACKFILL = """
UPDATE {table} x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE
"""

_ANON_BACKFILL = """
UPDATE {table} x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id
"""


def _add_tenant_to_table(table: str, *, has_anonymous: bool) -> None:
    op.add_column(
        table,
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
    op.execute(_PERSONAL_TENANT_BACKFILL.format(table=table))
    if has_anonymous:
        op.execute(_ANON_BACKFILL.format(table=table))
    op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL")


def upgrade() -> None:
    for tbl in (
        "product_info_jobs",
        "video_gen_tasks",
        "product_image_gen_tasks",
        "product_info_prompt_templates",
    ):
        _add_tenant_to_table(tbl, has_anonymous=True)

    op.add_column(
        "memories",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_memories_tenant_id", "memories", ["tenant_id"])
    op.execute(_PERSONAL_TENANT_BACKFILL.format(table="memories"))
    op.execute("ALTER TABLE memories ALTER COLUMN tenant_id SET NOT NULL")

    op.add_column(
        "api_keys",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.execute(
        """
        UPDATE api_keys x
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE t.owner_user_id = x.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE
        """
    )
    op.execute("ALTER TABLE api_keys ALTER COLUMN tenant_id SET NOT NULL")

    op.create_table(
        "system_mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("env_type", sa.String(50), nullable=False),
        sa.Column("env_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("template_id", sa.String(50), nullable=True),
        sa.Column("inherit_defaults", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("connection_status", sa.String(20), nullable=True),
        sa.Column("last_connected_at", sa.String(50), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("available_tools", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_system_mcp_servers_name", "system_mcp_servers", ["name"], unique=True)

    op.execute(
        """
        INSERT INTO system_mcp_servers (
            id, name, display_name, url, env_type, env_config, template_id,
            inherit_defaults, enabled, connection_status, last_connected_at,
            last_error, available_tools, description, category, created_at, updated_at
        )
        SELECT
            id, name, display_name, url, env_type, env_config, template_id,
            inherit_defaults, enabled, connection_status, last_connected_at,
            last_error, available_tools, description, category, created_at, updated_at
        FROM mcp_servers
        WHERE scope = 'system' OR user_id IS NULL
        """
    )
    op.execute("DELETE FROM mcp_servers WHERE scope = 'system' OR user_id IS NULL")

    _add_tenant_to_table("mcp_servers", has_anonymous=False)


def downgrade() -> None:
    op.drop_column("mcp_servers", "tenant_id")
    op.drop_table("system_mcp_servers")
    for tbl in (
        "api_keys",
        "memories",
        "product_info_prompt_templates",
        "product_image_gen_tasks",
        "video_gen_tasks",
        "product_info_jobs",
    ):
        op.drop_index(f"ix_{tbl}_tenant_id", table_name=tbl)
        op.drop_column(tbl, "tenant_id")
