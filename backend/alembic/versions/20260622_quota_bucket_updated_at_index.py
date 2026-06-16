"""add updated_at index on gateway_quota_plan_usage_buckets

Revision ID: 20260622_gqpub_uat
Revises: 20260621_dqbri
Create Date: 2026-06-22

清理 job 按 updated_at 删除过期行；补索引避免全表扫描。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260622_gqpub_uat"
down_revision: str | None = "20260621_dqbri"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_gateway_quota_plan_usage_buckets_updated_at",
        "gateway_quota_plan_usage_buckets",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gateway_quota_plan_usage_buckets_updated_at",
        table_name="gateway_quota_plan_usage_buckets",
    )
