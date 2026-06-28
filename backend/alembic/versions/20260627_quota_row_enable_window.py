"""quota rows: add enabled + valid_from/valid_until (per-row 启用停用与起止时间)

Revision ID: 20260627_qrew
Revises: 20260626_r2c
Create Date: 2026-06-27

为「配额中心一行 = 一条配额规则」补齐按行的启用停用与起止时间：
- ``gateway_budgets``：平台配额行；
- ``provider_plan_quotas`` / ``entitlement_plan_quotas``：上游 / 下游窗口配额行。

三表统一新增 ``enabled``（NOT NULL DEFAULT true，停用则不参与热路径执法）、
``valid_from`` / ``valid_until``（TIMESTAMPTZ NULL，NULL 表示该侧不限）。纯增量加列，
历史行 enabled 默认 true、起止时间为 NULL（= 始终有效，与现状一致）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260627_qrew"
down_revision: str | None = "20260626_r2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "gateway_budgets",
    "provider_plan_quotas",
    "entitlement_plan_quotas",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
        op.add_column(
            table,
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "valid_until")
        op.drop_column(table, "valid_from")
        op.drop_column(table, "enabled")
