"""Backfill gateway_request_logs.user_id from vkey / email / personal team owner

Revision ID: 20260528_bfrlu
Revises: 20260528_bfrlp2
Create Date: 2026-05-28

LiteLLM 回调丢失 ``gateway_user_id`` 时，personal team 调用仅保留 ``tenant_id``，
统计按人员维度出现「未关联人员」。本迁移回填历史行；新请求由 metadata/persist 修复。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_bfrlu"
down_revision: str | None = "20260528_bfrlp2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_STATEMENTS: tuple[str, ...] = (
    """
    UPDATE gateway_request_logs AS grl
    SET user_id = vk.created_by_user_id
    FROM gateway_virtual_keys AS vk
    WHERE grl.user_id IS NULL
      AND grl.vkey_id = vk.id
      AND vk.created_by_user_id IS NOT NULL
      AND vk.is_system = FALSE
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET user_id = u.id
    FROM users AS u
    WHERE grl.user_id IS NULL
      AND grl.user_email_snapshot IS NOT NULL
      AND u.email = grl.user_email_snapshot
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET user_id = gt.owner_user_id
    FROM gateway_teams AS gt
    WHERE grl.user_id IS NULL
      AND grl.tenant_id = gt.id
      AND gt.kind = 'personal'
    """,
)


def upgrade() -> None:
    conn = op.get_bind()
    for statement in _BACKFILL_STATEMENTS:
        conn.execute(sa.text(statement))


def downgrade() -> None:
    """数据回填不可逆。"""
