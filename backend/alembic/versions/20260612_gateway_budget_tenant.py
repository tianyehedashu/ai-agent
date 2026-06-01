"""gateway_budgets.tenant_id：按团队隔离成员总量/模型护栏

Revision ID: 20260612_gbt
Revises: 20260611_gbc
Create Date: 2026-06-12

- 新增 ``tenant_id``（nullable，无 DB FK）：仅 ``target_kind=user`` 且 ``credential_id IS NULL``
  的成员总量/模型护栏行非空，表示该护栏所属团队；其余维度恒 NULL。
- 两条 ``credential_id IS NULL`` 部分唯一索引改为含 ``COALESCE(tenant_id, 全零 UUID)``，
  使同一成员在不同团队的护栏行可并存，而非 user 维度（tenant_id 恒 NULL）唯一性不变。
- 单一语义、无回填：历史 ``tenant_id IS NULL`` 的成员护栏行不再被热路径匹配（需在团队内重建）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260612_gbt"
down_revision: str | None = "20260611_gbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SENTINEL = "00000000-0000-0000-0000-000000000000"
_COALESCE = f"coalesce(tenant_id, '{_TENANT_SENTINEL}'::uuid)"


def upgrade() -> None:
    op.add_column(
        "gateway_budgets",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_gateway_budgets_tenant_id",
        "gateway_budgets",
        ["tenant_id"],
    )

    # 成员总量/模型护栏唯一索引按团队隔离（含 COALESCE(tenant_id, 全零)）。
    op.drop_index("uq_gateway_budgets_target_period_agg", table_name="gateway_budgets")
    op.drop_index("uq_gateway_budgets_target_period_model", table_name="gateway_budgets")
    op.create_index(
        "uq_gateway_budgets_target_period_agg",
        "gateway_budgets",
        ["target_kind", "target_id", sa.text(_COALESCE), "period"],
        unique=True,
        postgresql_where=sa.text("model_name IS NULL AND credential_id IS NULL"),
    )
    op.create_index(
        "uq_gateway_budgets_target_period_model",
        "gateway_budgets",
        ["target_kind", "target_id", sa.text(_COALESCE), "period", "model_name"],
        unique=True,
        postgresql_where=sa.text("model_name IS NOT NULL AND credential_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_gateway_budgets_target_period_model", table_name="gateway_budgets")
    op.drop_index("uq_gateway_budgets_target_period_agg", table_name="gateway_budgets")
    op.create_index(
        "uq_gateway_budgets_target_period_agg",
        "gateway_budgets",
        ["target_kind", "target_id", "period"],
        unique=True,
        postgresql_where=sa.text("model_name IS NULL AND credential_id IS NULL"),
    )
    op.create_index(
        "uq_gateway_budgets_target_period_model",
        "gateway_budgets",
        ["target_kind", "target_id", "period", "model_name"],
        unique=True,
        postgresql_where=sa.text("model_name IS NOT NULL AND credential_id IS NULL"),
    )

    op.drop_index("ix_gateway_budgets_tenant_id", table_name="gateway_budgets")
    op.drop_column("gateway_budgets", "tenant_id")
