"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

新表约定（多租户业务表）:
  id UUID PK, created_at/updated_at TIMESTAMPTZ NOT NULL,
  tenant_id UUID NOT NULL（系统级配置用 system_* 表，勿 tenant_id NULL）
策略挂载表可另加 target_kind/target_id；禁止新增 user_id/team_id/scope/scope_id 列名。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
