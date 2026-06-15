"""回填团队凭据 created_by_user_id（清理 legacy 共享凭据）

Revision ID: 20260619_tccb
Revises: 20260618_pop
Create Date: 2026-06-19

迁移前 ``created_by_user_id IS NULL`` 的团队凭据按 legacy 规则由 admin+ 管理。
本迁移将其归属回填为团队 ``owner_user_id``，以便统一走创建者私有 RBAC。

**发布顺序**：须与本 revision 对应的应用代码同批部署，或先执行本迁移再部署代码；
切勿先部署移除 legacy 规则的代码再补跑迁移。

本迁移不可逆（``downgrade`` 为空）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from utils.logging import get_logger

logger = get_logger(__name__)

revision: str = "20260619_tccb"
down_revision: str | None = "20260618_pop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE provider_credentials pc
        SET created_by_user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE pc.tenant_id = t.id
          AND pc.scope = 'team'
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
          AND pc.scope = 'team'
          AND pc.created_by_user_id IS NULL
        """
    )

    connection = op.get_bind()
    remaining = connection.execute(
        sa.text(
            """
            SELECT count(*) FROM provider_credentials
            WHERE scope = 'team' AND created_by_user_id IS NULL
            """
        )
    ).scalar()
    if remaining and int(remaining) > 0:
        logger.warning(
            "backfill_team_credential_creators: %s team credentials still have "
            "NULL created_by_user_id; manual assignment required",
            remaining,
        )
    else:
        logger.info("backfill_team_credential_creators: completed, no NULL team credentials remain")


def downgrade() -> None:
    pass
