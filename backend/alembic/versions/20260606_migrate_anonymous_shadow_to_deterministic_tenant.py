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
from domains.identity.domain.anonymous_tenant import resolve_anonymous_tenant_id
from domains.identity.domain.orphan_tenant_tables import TENANT_SCOPED_TABLES_FOR_MIGRATION

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "20260606_anon_tenant"
down_revision: str | None = "20260605_sys_cred_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
