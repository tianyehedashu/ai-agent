"""add limit_images / image_count for image generation quota

Revision ID: 20260704_lim
Revises: 20260703_mhro
Create Date: 2026-07-04

为图片生成模型引入"张数"配额维度：

- ``gateway_budgets`` 增加 ``limit_images`` / ``current_images``
- ``entitlement_plan_quotas`` 增加 ``limit_images``
- ``provider_quotas`` 增加 ``limit_images``
- ``gateway_request_logs`` 增加 ``image_count``（按月分区主表加列，PG 15+ 自动级联）

所有新列均 ``nullable`` 或带 ``server_default``，存量行无需回填即可生效。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260704_lim"
down_revision: str | None = "20260703_mhro"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # gateway_budgets：限额 + 当前用量
    op.add_column(
        "gateway_budgets",
        sa.Column("limit_images", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gateway_budgets",
        sa.Column(
            "current_images",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # entitlement_plan_quotas：限额
    op.add_column(
        "entitlement_plan_quotas",
        sa.Column("limit_images", sa.Integer(), nullable=True),
    )

    # provider_quotas：限额
    op.add_column(
        "provider_quotas",
        sa.Column("limit_images", sa.Integer(), nullable=True),
    )

    # gateway_request_logs：单次调用生成图片张数（分区主表加列自动级联子分区）
    op.add_column(
        "gateway_request_logs",
        sa.Column(
            "image_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # gateway_quota_plan_usage_buckets：窗口用量汇总增加 images 列
    op.add_column(
        "gateway_quota_plan_usage_buckets",
        sa.Column(
            "images",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("gateway_quota_plan_usage_buckets", "images")
    op.drop_column("gateway_request_logs", "image_count")
    op.drop_column("provider_quotas", "limit_images")
    op.drop_column("entitlement_plan_quotas", "limit_images")
    op.drop_column("gateway_budgets", "current_images")
    op.drop_column("gateway_budgets", "limit_images")
