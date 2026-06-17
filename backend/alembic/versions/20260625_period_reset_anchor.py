"""gateway_budgets / plan quotas: period reset anchor columns

Revision ID: 20260625_pra
Revises: 20260624_gmhrp
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260625_pra"
down_revision: str | None = "20260624_gmhrp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_budgets",
        sa.Column(
            "period_timezone",
            sa.String(length=64),
            server_default="UTC",
            nullable=False,
        ),
    )
    op.add_column(
        "gateway_budgets",
        sa.Column(
            "period_reset_minutes",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "gateway_budgets",
        sa.Column(
            "period_reset_day",
            sa.SmallInteger(),
            server_default="1",
            nullable=False,
        ),
    )
    for table in ("provider_plan_quotas", "entitlement_plan_quotas"):
        op.add_column(
            table,
            sa.Column(
                "reset_timezone",
                sa.String(length=64),
                server_default="UTC",
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "reset_time_minutes",
                sa.SmallInteger(),
                server_default="0",
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "reset_day_of_month",
                sa.SmallInteger(),
                server_default="1",
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_column("gateway_budgets", "period_reset_day")
    op.drop_column("gateway_budgets", "period_reset_minutes")
    op.drop_column("gateway_budgets", "period_timezone")
    for table in ("provider_plan_quotas", "entitlement_plan_quotas"):
        op.drop_column(table, "reset_day_of_month")
        op.drop_column(table, "reset_time_minutes")
        op.drop_column(table, "reset_timezone")
