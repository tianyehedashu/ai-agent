"""Migrate anonymous shadow users to deterministic orphan tenant_id; drop shadow rows.

Revision ID: 20260606_anon_tenant
Revises: 20260605_sys_cred_models
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "20260606_anon_tenant"
down_revision: str | None = "20260605_sys_cred_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 历史迁移自包含：匿名能力已移除，此处内联当时的常量/算法以保持本迁移可重放。
_ANONYMOUS_TENANT_NAMESPACE = uuid.UUID("01932f8a-7b3c-7000-8000-000000000001")
_ANONYMOUS_ID_PREFIX = "anonymous-"
TENANT_SCOPED_TABLES_FOR_MIGRATION: tuple[str, ...] = (
    "sessions",
    "agents",
    "video_gen_tasks",
    "product_image_gen_tasks",
    "product_info_jobs",
    "product_info_prompt_templates",
    "memories",
    "mcp_servers",
    "api_keys",
    "api_key_gateway_grants",
    "gateway_models",
    "gateway_routes",
    "gateway_virtual_keys",
    "gateway_alert_rules",
    "provider_credentials",
    "gateway_alert_events",
)


def resolve_anonymous_tenant_id(cookie_id: str) -> uuid.UUID:
    """由匿名 cookie ID 确定性解析 orphan tenant_id（历史迁移内联，UUID v5）。"""
    normalized = cookie_id.strip()
    if normalized.startswith(_ANONYMOUS_ID_PREFIX):
        normalized = normalized[len(_ANONYMOUS_ID_PREFIX) :]
    return uuid.uuid5(_ANONYMOUS_TENANT_NAMESPACE, normalized)


def _existing_tenant_tables(conn: sa.Connection) -> tuple[str, ...]:
    """仅更新当前库中已存在的 tenant 表（兼容分支/环境差异）。"""
    inspector = sa.inspect(conn)
    names = set(inspector.get_table_names())
    return tuple(t for t in TENANT_SCOPED_TABLES_FOR_MIGRATION if t in names)


def upgrade() -> None:
    conn = op.get_bind()
    tenant_tables = _existing_tenant_tables(conn)
    rows = (
        conn.execute(
            sa.text(
                """
            SELECT u.id AS user_id,
                   u.settings->>'anonymous_cookie_id' AS cookie_id,
                   t.id AS team_id
            FROM users u
            LEFT JOIN gateway_teams t
                ON t.owner_user_id = u.id
               AND t.kind = 'personal'
               AND t.is_active = TRUE
            WHERE u.role = 'anonymous'
              AND u.settings->>'anonymous_cookie_id' IS NOT NULL
            """
            )
        )
        .mappings()
        .all()
    )

    shadow_team_ids: set[uuid.UUID] = set()
    shadow_user_ids: set[uuid.UUID] = set()

    for row in rows:
        cookie_id = row["cookie_id"]
        if not cookie_id:
            continue
        new_tenant = resolve_anonymous_tenant_id(str(cookie_id))
        old_tenant = row["team_id"]
        if old_tenant is not None and uuid.UUID(str(old_tenant)) != new_tenant:
            for table in tenant_tables:
                conn.execute(
                    sa.text(
                        f"""
                        UPDATE {table}
                        SET tenant_id = :new_tenant
                        WHERE tenant_id = :old_tenant
                        """
                    ),
                    {"new_tenant": new_tenant, "old_tenant": old_tenant},
                )
            shadow_team_ids.add(uuid.UUID(str(old_tenant)))

        shadow_user_ids.add(uuid.UUID(str(row["user_id"])))

    for team_id in shadow_team_ids:
        conn.execute(
            sa.text("DELETE FROM gateway_team_members WHERE team_id = :team_id"),
            {"team_id": team_id},
        )
        conn.execute(
            sa.text("DELETE FROM gateway_teams WHERE id = :team_id"),
            {"team_id": team_id},
        )

    for user_id in shadow_user_ids:
        conn.execute(
            sa.text("DELETE FROM users WHERE id = :user_id AND role = 'anonymous'"),
            {"user_id": user_id},
        )


def downgrade() -> None:
    # 不可逆：shadow User 已删除，deterministic tenant 数据保留为 orphan tenant。
    pass
