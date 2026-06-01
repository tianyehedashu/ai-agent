"""gateway_budgets.credential_id + 成员凭据维度部分唯一索引

Revision ID: 20260611_gbc
Revises: 20260610_del_probe_logs
Create Date: 2026-06-11

- ``credential_id`` 非空：仅与 ``target_kind=user`` 组合，表示「成员 + 凭据(+ 模型)」专属预算行。
- 现有两条部分唯一索引收紧为 ``credential_id IS NULL``，避免成员总量行与成员+凭据行键冲突；
  新增两条 ``credential_id IS NOT NULL`` 索引保证凭据维度唯一性。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260611_gbc"
down_revision: str | None = "20260610_del_probe_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_budgets",
        sa.Column("credential_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_gateway_budgets_credential_id",
        "gateway_budgets",
        ["credential_id"],
    )

    # 现有汇总/模型索引收紧为 credential_id IS NULL
    op.drop_index("uq_gateway_budgets_target_period_agg", table_name="gateway_budgets")
    op.drop_index("uq_gateway_budgets_target_period_model", table_name="gateway_budgets")
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

    # 新增成员+凭据维度索引
    op.create_index(
        "uq_gateway_budgets_target_period_cred_agg",
        "gateway_budgets",
        ["target_kind", "target_id", "period", "credential_id"],
        unique=True,
        postgresql_where=sa.text("model_name IS NULL AND credential_id IS NOT NULL"),
    )
    op.create_index(
        "uq_gateway_budgets_target_period_cred_model",
        "gateway_budgets",
        ["target_kind", "target_id", "period", "credential_id", "model_name"],
        unique=True,
        postgresql_where=sa.text("model_name IS NOT NULL AND credential_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_gateway_budgets_target_period_cred_model", table_name="gateway_budgets"
    )
    op.drop_index(
        "uq_gateway_budgets_target_period_cred_agg", table_name="gateway_budgets"
    )
    op.drop_index("uq_gateway_budgets_target_period_model", table_name="gateway_budgets")
    op.drop_index("uq_gateway_budgets_target_period_agg", table_name="gateway_budgets")
    op.create_index(
        "uq_gateway_budgets_target_period_agg",
        "gateway_budgets",
        ["target_kind", "target_id", "period"],
        unique=True,
        postgresql_where=sa.text("model_name IS NULL"),
    )
    op.create_index(
        "uq_gateway_budgets_target_period_model",
        "gateway_budgets",
        ["target_kind", "target_id", "period", "model_name"],
        unique=True,
        postgresql_where=sa.text("model_name IS NOT NULL"),
    )

    op.drop_index("ix_gateway_budgets_credential_id", table_name="gateway_budgets")
    op.drop_column("gateway_budgets", "credential_id")
