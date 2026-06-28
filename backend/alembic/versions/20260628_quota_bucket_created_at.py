"""add created_at on gateway_quota_plan_usage_buckets

Revision ID: 20260628_gqpub_cat
Revises: 20260704_lim
Create Date: 2026-06-28

业务表需同时具备 created_at/updated_at（架构规范 test_business_tables_have_timestamps）。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260628_gqpub_cat"
down_revision: str | None = "20260704_lim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_quota_plan_usage_buckets",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "gateway_quota_plan_usage_buckets",
        "created_at",
    )
