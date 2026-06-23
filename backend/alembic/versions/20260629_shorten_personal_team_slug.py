"""缩短个人团队 slug：personal-<完整UUID> → personal-<hex8>

Revision ID: 20260629_ptsl
Revises: 20260622_grl_user_ix
Create Date: 2026-06-29

个人团队 slug 历史上用完整 ``owner_user_id``，使跨团队 vkey 的模型前缀
``<slug>/<model>`` 过长（如 ``personal-877ae63a-985c-4e4e-9425-986f79e944cc/agnes``）。
本迁移将其收敛为 ``personal-<前 8 位 hex>``，与共享团队 ``team-<hex8>`` 对齐，且与
``domains.tenancy.domain.policies.team_slug.personal_team_slug`` 的生成规则一致。

slug 仅作展示与派发前缀，租户解析始终走 ``tenant_id`` 并在列表/派发时实时读取 slug，
故重命名对鉴权与既有授权无副作用；唯一影响是客户端须改用新短前缀（即本次目的）。

仅改写「自动生成的长 slug」（``slug = 'personal-' || owner_user_id``），不动任何
自定义 slug；幂等且可逆（downgrade 按相同规则还原长 slug）。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260629_ptsl"
down_revision: str | None = "20260622_grl_user_ix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE gateway_teams
        SET slug = 'personal-' || substr(replace(owner_user_id::text, '-', ''), 1, 8)
        WHERE kind = 'personal'
          AND slug = 'personal-' || owner_user_id::text
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE gateway_teams
        SET slug = 'personal-' || owner_user_id::text
        WHERE kind = 'personal'
          AND slug = 'personal-' || substr(replace(owner_user_id::text, '-', ''), 1, 8)
        """
    )
