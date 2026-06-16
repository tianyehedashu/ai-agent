"""drop redundant ix on gateway_quota_plan_usage_buckets

Revision ID: 20260621_dqbri
Revises: 20260620_gqpub
Create Date: 2026-06-21

读路径走 PK 点查；(ns, plan_id) 次要索引仅增加写放大，无查询使用。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260621_dqbri"
down_revision: str | None = "20260620_gqpub"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_gateway_quota_plan_usage_buckets_ns_plan",
        table_name="gateway_quota_plan_usage_buckets",
        if_exists=True,
    )


def downgrade() -> None:
    op.create_index(
        "ix_gateway_quota_plan_usage_buckets_ns_plan",
        "gateway_quota_plan_usage_buckets",
        ["ns", "plan_id"],
        unique=False,
    )
