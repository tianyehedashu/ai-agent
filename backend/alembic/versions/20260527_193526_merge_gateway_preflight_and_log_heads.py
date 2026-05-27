"""merge_gateway_preflight_and_log_heads

Revision ID: f31bf0379153
Revises: 20260528_bfrlu, 20260607_gw_pref_idx, 20260607_tenant_route
Create Date: 2026-05-27 19:35:26.088488

新表约定（多租户业务表）:
  id UUID PK, created_at/updated_at TIMESTAMPTZ NOT NULL,
  tenant_id UUID NOT NULL（系统级配置用 system_* 表，勿 tenant_id NULL）
策略挂载表可另加 target_kind/target_id；禁止新增 user_id/team_id/scope/scope_id 列名。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f31bf0379153'
down_revision: Union[str, None] = ('20260528_bfrlu', '20260607_gw_pref_idx', '20260607_tenant_route')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
