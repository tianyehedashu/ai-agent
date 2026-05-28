"""gateway: provider_plans + entitlement_plans (symmetric two-side plans)

Revision ID: 20260518_gpep
Revises: 20260515_drop_pc_lum
Create Date: 2026-05-18

引入对称双层套餐：
- provider_plans / provider_plan_quotas — 上游（绑 credential, real_model?）
- entitlement_plans / entitlement_plan_quotas — 下游（绑 vkey / apikey_grant）
- gateway_request_logs / gateway_metrics_hourly 增列 entitlement_plan_id /
  provider_plan_id，使 rollup 与统计能按双侧对齐。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260518_gpep"
down_revision: str | None = "20260515_drop_pc_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # provider_plans
    # ------------------------------------------------------------------
    op.create_table(
        "provider_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("real_model", sa.String(length=200), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_provider_plans_credential_id", "provider_plans", ["credential_id"])
    op.create_index(
        "ix_provider_plans_active",
        "provider_plans",
        ["credential_id", "real_model", "is_active", "valid_from", "valid_until"],
    )

    op.create_table(
        "provider_plan_quotas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "reset_strategy",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'rolling'"),
        ),
        sa.Column("limit_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("limit_tokens", sa.Integer(), nullable=True),
        sa.Column("limit_requests", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("plan_id", "label", name="uq_provider_plan_quota_label"),
    )
    op.create_index("ix_provider_plan_quotas_plan_id", "provider_plan_quotas", ["plan_id"])

    # ------------------------------------------------------------------
    # entitlement_plans
    # ------------------------------------------------------------------
    op.create_table(
        "entitlement_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column(
            "included_models",
            postgresql.ARRAY(sa.String(length=200)),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
        sa.Column(
            "included_capabilities",
            postgresql.ARRAY(sa.String(length=40)),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_entitlement_plans_scope_id", "entitlement_plans", ["scope_id"])
    op.create_index(
        "ix_entitlement_plans_active",
        "entitlement_plans",
        ["scope", "scope_id", "is_active", "valid_from", "valid_until"],
    )

    op.create_table(
        "entitlement_plan_quotas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entitlement_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "reset_strategy",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'rolling'"),
        ),
        sa.Column("limit_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("limit_tokens", sa.Integer(), nullable=True),
        sa.Column("limit_requests", sa.Integer(), nullable=True),
        sa.Column("unit_price_usd_per_token", sa.Numeric(12, 8), nullable=True),
        sa.Column("unit_price_usd_per_request", sa.Numeric(12, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("plan_id", "label", name="uq_entitlement_plan_quota_label"),
    )
    op.create_index(
        "ix_entitlement_plan_quotas_plan_id",
        "entitlement_plan_quotas",
        ["plan_id"],
    )

    # ------------------------------------------------------------------
    # request log + metrics_hourly: 双向计量列
    # ------------------------------------------------------------------
    op.add_column(
        "gateway_request_logs",
        sa.Column("entitlement_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gateway_request_logs",
        sa.Column("provider_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_gateway_request_logs_entitlement_time",
        "gateway_request_logs",
        ["entitlement_plan_id", "created_at"],
    )
    op.create_index(
        "ix_gateway_request_logs_provider_plan_time",
        "gateway_request_logs",
        ["provider_plan_id", "created_at"],
    )

    op.add_column(
        "gateway_metrics_hourly",
        sa.Column("entitlement_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column("provider_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.drop_constraint("uq_gateway_metrics_hourly_dim", "gateway_metrics_hourly", type_="unique")
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "team_id",
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


def downgrade() -> None:
    op.drop_constraint("uq_gateway_metrics_hourly_dim", "gateway_metrics_hourly", type_="unique")
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "team_id",
            "user_id",
            "vkey_id",
            "credential_id",
            "provider",
            "real_model",
            "capability",
        ],
    )
    op.drop_column("gateway_metrics_hourly", "provider_plan_id")
    op.drop_column("gateway_metrics_hourly", "entitlement_plan_id")

    op.drop_index(
        "ix_gateway_request_logs_provider_plan_time",
        table_name="gateway_request_logs",
    )
    op.drop_index(
        "ix_gateway_request_logs_entitlement_time",
        table_name="gateway_request_logs",
    )
    op.drop_column("gateway_request_logs", "provider_plan_id")
    op.drop_column("gateway_request_logs", "entitlement_plan_id")

    op.drop_index("ix_entitlement_plan_quotas_plan_id", table_name="entitlement_plan_quotas")
    op.drop_table("entitlement_plan_quotas")
    op.drop_index("ix_entitlement_plans_active", table_name="entitlement_plans")
    op.drop_index("ix_entitlement_plans_scope_id", table_name="entitlement_plans")
    op.drop_table("entitlement_plans")

    op.drop_index("ix_provider_plan_quotas_plan_id", table_name="provider_plan_quotas")
    op.drop_table("provider_plan_quotas")
    op.drop_index("ix_provider_plans_active", table_name="provider_plans")
    op.drop_index("ix_provider_plans_credential_id", table_name="provider_plans")
    op.drop_table("provider_plans")
