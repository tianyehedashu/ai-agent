"""Rename gateway_budgets scope/scope_id to target_kind/target_id

Revision ID: 20260529_gbrt
Revises: 20260528_sgmcf
Create Date: 2026-05-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260529_gbrt"
down_revision: str | None = "20260528_sgmcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("gateway_budgets", "scope", new_column_name="target_kind")
    op.alter_column("gateway_budgets", "scope_id", new_column_name="target_id")
    op.execute(
        """
        UPDATE gateway_budgets SET target_kind = 'tenant' WHERE target_kind = 'team'
        """
    )
    op.execute(
        "ALTER INDEX uq_gateway_budgets_scope_period_agg "
        "RENAME TO uq_gateway_budgets_target_period_agg"
    )
    op.execute(
        "ALTER INDEX uq_gateway_budgets_scope_period_model "
        "RENAME TO uq_gateway_budgets_target_period_model"
    )
    op.execute(
        "ALTER INDEX ix_gateway_budgets_lookup "
        "RENAME TO ix_gateway_budgets_target_lookup"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_gateway_budgets_target_lookup "
        "RENAME TO ix_gateway_budgets_lookup"
    )
    op.execute(
        "ALTER INDEX uq_gateway_budgets_target_period_model "
        "RENAME TO uq_gateway_budgets_scope_period_model"
    )
    op.execute(
        "ALTER INDEX uq_gateway_budgets_target_period_agg "
        "RENAME TO uq_gateway_budgets_scope_period_agg"
    )
    op.execute(
        """
        UPDATE gateway_budgets SET target_kind = 'team' WHERE target_kind = 'tenant'
        """
    )
    op.alter_column("gateway_budgets", "target_id", new_column_name="scope_id")
    op.alter_column("gateway_budgets", "target_kind", new_column_name="scope")
