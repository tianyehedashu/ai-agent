"""回填 tenant_id 非空但 scope 未标 team 的凭据 created_by_user_id

Revision ID: 20260622_btcc
Revises: 8418cdb1fed7
Create Date: 2026-06-22

``20260619_tccb`` 仅覆盖 ``scope = 'team'``；历史行常见 ``scope IS NULL`` 且
``tenant_id`` 已设（如 huoshan-common），导致 created_by_user_id 仍为 NULL。
本迁移按 tenant 归属回填创建者，与 tccb 第二步 admin/owner 回退一致。

本迁移不可逆（``downgrade`` 为空）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from utils.logging import get_logger

logger = get_logger(__name__)

revision: str = "20260622_btcc"
down_revision: str | None = "8418cdb1fed7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE provider_credentials pc
        SET created_by_user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE pc.tenant_id = t.id
          AND pc.tenant_id IS NOT NULL
          AND (pc.scope IS NULL OR pc.scope = 'team')
          AND pc.created_by_user_id IS NULL
          AND t.owner_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE provider_credentials pc
        SET created_by_user_id = sub.user_id
        FROM (
            SELECT DISTINCT ON (m.team_id)
                m.team_id,
                m.user_id
            FROM gateway_team_members m
            WHERE m.role IN ('owner', 'admin')
            ORDER BY m.team_id, (m.role = 'owner') DESC, m.created_at ASC
        ) sub
        WHERE pc.tenant_id = sub.team_id
          AND pc.tenant_id IS NOT NULL
          AND (pc.scope IS NULL OR pc.scope = 'team')
          AND pc.created_by_user_id IS NULL
        """
    )

    connection = op.get_bind()
    remaining = connection.execute(
        sa.text(
            """
            SELECT count(*) FROM provider_credentials
            WHERE tenant_id IS NOT NULL
              AND (scope IS NULL OR scope = 'team')
              AND created_by_user_id IS NULL
            """
        )
    ).scalar()
    if remaining and int(remaining) > 0:
        logger.warning(
            "backfill_tenant_credential_creators: %s tenant credentials still have "
            "NULL created_by_user_id; manual assignment required",
            remaining,
        )
    else:
        logger.info(
            "backfill_tenant_credential_creators: completed, no NULL tenant credentials remain"
        )


def downgrade() -> None:
    pass
