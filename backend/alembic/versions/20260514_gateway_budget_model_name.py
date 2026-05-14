"""gateway_budgets optional model_name + partial unique indexes

Revision ID: 20260514_gbm
Revises: 20260514_dsw
Create Date: 2026-05-14

- ``model_name`` NULL：全模型汇总预算（与历史行为一致）
- ``model_name`` 非空：仅对该请求 ``model`` 字符串计量的预算行

唯一性由两条 PostgreSQL 部分唯一索引保证（避免 UNIQUE 与多 NULL 语义问题）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_gbm"
down_revision: str | None = "20260514_dsw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_budgets",
        sa.Column("model_name", sa.String(200), nullable=True),
    )
    op.drop_constraint(
        "uq_gateway_budgets_scope_period",
        "gateway_budgets",
        type_="unique",
    )
    op.create_index(
        "uq_gateway_budgets_scope_period_agg",
        "gateway_budgets",
        ["scope", "scope_id", "period"],
        unique=True,
        postgresql_where=sa.text("model_name IS NULL"),
    )
    op.create_index(
        "uq_gateway_budgets_scope_period_model",
        "gateway_budgets",
        ["scope", "scope_id", "period", "model_name"],
        unique=True,
        postgresql_where=sa.text("model_name IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_gateway_budgets_scope_period_model",
        table_name="gateway_budgets",
    )
    op.drop_index(
        "uq_gateway_budgets_scope_period_agg",
        table_name="gateway_budgets",
    )
    op.create_unique_constraint(
        "uq_gateway_budgets_scope_period",
        "gateway_budgets",
        ["scope", "scope_id", "period"],
    )
    op.drop_column("gateway_budgets", "model_name")
