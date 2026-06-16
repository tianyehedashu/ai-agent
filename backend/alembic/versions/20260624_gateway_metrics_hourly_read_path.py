"""gateway_metrics_hourly read-path columns + gateway_rollup_state

Revision ID: 20260624_gmhrp
Revises: 20260623_apprm
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260624_gmhrp"
down_revision: str | None = "20260623_apprm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column(
            "revenue_usd",
            sa.Numeric(precision=14, scale=6),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column(
            "ttfb_total_ms",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column("model_key", sa.String(length=200), nullable=True),
    )

    op.execute(
        """
        UPDATE gateway_metrics_hourly
        SET model_key = COALESCE(NULLIF(TRIM(real_model), ''), 'unknown')
        WHERE model_key IS NULL
        """
    )
    op.alter_column("gateway_metrics_hourly", "model_key", nullable=False)

    op.drop_constraint("uq_gateway_metrics_hourly_dim", "gateway_metrics_hourly", type_="unique")
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "tenant_id",
            "user_id",
            "vkey_id",
            "credential_id",
            "entitlement_plan_id",
            "provider_plan_id",
            "provider",
            "model_key",
            "capability",
        ],
    )

    op.create_table(
        "gateway_rollup_state",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("last_rolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_gateway_rollup_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO gateway_rollup_state (id, last_rolled_at)
        VALUES (1, date_trunc('hour', NOW() AT TIME ZONE 'UTC') - INTERVAL '48 hours')
        """
    )


def downgrade() -> None:
    op.drop_table("gateway_rollup_state")

    op.drop_constraint("uq_gateway_metrics_hourly_dim", "gateway_metrics_hourly", type_="unique")
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "tenant_id",
            "user_id",
            "vkey_id",
            "credential_id",
            "entitlement_plan_id",
            "provider_plan_id",
            "provider",
            "real_model",
            "capability",
        ],
    )
    op.drop_column("gateway_metrics_hourly", "model_key")
    op.drop_column("gateway_metrics_hourly", "ttfb_total_ms")
    op.drop_column("gateway_metrics_hourly", "revenue_usd")
