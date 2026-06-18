"""flatten upstream: provider_plans+quotas → provider_quotas; entitlement plan containerize

Revision ID: 20260628_fpq
Revises: 20260627_qrew
Create Date: 2026-06-28

- 新建扁平 ``provider_quotas``，删除 ``provider_plans`` / ``provider_plan_quotas``。
- ``entitlement_plans`` 删除 ``is_active`` / ``valid_until`` / ``auto_renew``（plan 头退化为容器）。
- 无数据迁移（生产配额已清空）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_fpq"
down_revision: str | None = "20260627_qrew"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_quotas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("real_model", sa.String(length=200), nullable=True),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "reset_strategy",
            sa.String(length=32),
            nullable=False,
            server_default="rolling",
        ),
        sa.Column(
            "reset_timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
        ),
        sa.Column(
            "reset_time_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reset_day_of_month",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("limit_usd", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("limit_tokens", sa.Integer(), nullable=True),
        sa.Column("limit_requests", sa.Integer(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_provider_quota_cred_model_label "
        "ON provider_quotas (credential_id, COALESCE(real_model, ''), label)"
    )
    op.create_index(
        "ix_provider_quotas_cred_model_enabled",
        "provider_quotas",
        ["credential_id", "real_model", "enabled"],
    )
    op.create_index(
        op.f("ix_provider_quotas_credential_id"),
        "provider_quotas",
        ["credential_id"],
    )

    op.drop_table("provider_plan_quotas")
    op.drop_table("provider_plans")

    op.drop_index("ix_entitlement_plans_lifecycle", table_name="entitlement_plans")
    op.drop_column("entitlement_plans", "auto_renew")
    op.drop_column("entitlement_plans", "valid_until")
    op.drop_column("entitlement_plans", "is_active")


def downgrade() -> None:
    raise NotImplementedError("flatten provider_quotas is not reversible without data loss")
