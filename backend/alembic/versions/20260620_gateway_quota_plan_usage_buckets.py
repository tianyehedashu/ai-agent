"""gateway_quota_plan_usage_buckets: 上下游配额窗口用量汇总

Revision ID: 20260620_gqpub
Revises: 20260619_tccb
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260620_gqpub"
down_revision: str | None = "20260619_tccb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gateway_quota_plan_usage_buckets",
        sa.Column("ns", sa.String(length=16), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("requests", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=14, scale=6), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ns", "plan_id", "quota_id", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("gateway_quota_plan_usage_buckets")
