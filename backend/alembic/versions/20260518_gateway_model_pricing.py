"""gateway: upstream/downstream model pricing + log revenue + budget soft limit

Revision ID: 20260518_gmp
Revises: 20260518_gpep
Create Date: 2026-05-18

- upstream_model_pricing / downstream_model_pricing
- gateway_request_logs: revenue_usd, pricing_snapshot
- gateway_budgets: soft_limit_usd, max_parallel_requests, budget_reset_at
- 数据迁移：GatewayModel.tags 中的 input_cost_per_token 迁入 upstream_model_pricing
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260518_gmp"
down_revision: str | None = "20260518_gpep"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upstream_model_pricing",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("upstream_model", sa.String(length=200), nullable=False),
        sa.Column(
            "capability",
            sa.String(length=40),
            nullable=False,
            server_default="chat",
        ),
        sa.Column("input_cost_per_token", sa.Numeric(precision=14, scale=10), nullable=False),
        sa.Column("output_cost_per_token", sa.Numeric(precision=14, scale=10), nullable=False),
        sa.Column(
            "cache_creation_input_token_cost",
            sa.Numeric(precision=14, scale=10),
            nullable=True,
        ),
        sa.Column(
            "cache_read_input_token_cost",
            sa.Numeric(precision=14, scale=10),
            nullable=True,
        ),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="manual",
        ),
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
        sa.UniqueConstraint(
            "provider",
            "upstream_model",
            "capability",
            "effective_from",
            name="uq_upstream_model_pricing_natural",
        ),
    )
    op.create_index(
        "ix_upstream_model_pricing_provider",
        "upstream_model_pricing",
        ["provider"],
    )
    op.create_index(
        "ix_upstream_model_pricing_upstream_model",
        "upstream_model_pricing",
        ["upstream_model"],
    )
    op.create_index(
        "ix_upstream_model_pricing_lookup",
        "upstream_model_pricing",
        ["provider", "upstream_model", "capability", "effective_from", "effective_to"],
    )

    op.create_table(
        "downstream_model_pricing",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "gateway_model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_models.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("input_cost_per_token", sa.Numeric(precision=14, scale=10), nullable=True),
        sa.Column("output_cost_per_token", sa.Numeric(precision=14, scale=10), nullable=True),
        sa.Column(
            "cache_creation_input_token_cost",
            sa.Numeric(precision=14, scale=10),
            nullable=True,
        ),
        sa.Column(
            "cache_read_input_token_cost",
            sa.Numeric(precision=14, scale=10),
            nullable=True,
        ),
        sa.Column("per_request_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column(
            "inheritance_strategy",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.UniqueConstraint(
            "scope",
            "scope_id",
            "gateway_model_id",
            "effective_from",
            name="uq_downstream_model_pricing_natural",
        ),
        sa.CheckConstraint(
            "(inheritance_strategy = 'manual' AND input_cost_per_token IS NOT NULL "
            "AND output_cost_per_token IS NOT NULL) OR "
            "(inheritance_strategy = 'mirror' AND input_cost_per_token IS NULL "
            "AND output_cost_per_token IS NULL "
            "AND cache_creation_input_token_cost IS NULL "
            "AND cache_read_input_token_cost IS NULL)",
            name="ck_downstream_pricing_strategy_columns",
        ),
    )
    op.create_index(
        "ix_downstream_model_pricing_scope_id", "downstream_model_pricing", ["scope_id"]
    )
    op.create_index(
        "ix_downstream_model_pricing_gateway_model_id",
        "downstream_model_pricing",
        ["gateway_model_id"],
    )
    op.create_index(
        "ix_downstream_model_pricing_lookup",
        "downstream_model_pricing",
        ["scope", "scope_id", "gateway_model_id", "effective_from", "effective_to"],
    )

    op.add_column(
        "gateway_request_logs",
        sa.Column(
            "revenue_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "gateway_request_logs",
        sa.Column("pricing_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.add_column(
        "gateway_budgets",
        sa.Column("soft_limit_usd", sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        "gateway_budgets",
        sa.Column("max_parallel_requests", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gateway_budgets",
        sa.Column("budget_reset_at", sa.DateTime(timezone=True), nullable=True),
    )

    _migrate_tags_to_upstream_pricing()


def _migrate_tags_to_upstream_pricing() -> None:
    """从 gateway_models.tags 迁入已有 input_cost_per_token（config-managed 行）。"""
    conn = op.get_bind()
    now = datetime.now(UTC)
    rows = conn.execute(
        sa.text(
            """
            SELECT id, provider, real_model, capability, tags
            FROM gateway_models
            WHERE tags IS NOT NULL
              AND team_id IS NULL
            """
        )
    ).fetchall()
    for row in rows:
        tags = row.tags
        if tags is None:
            continue
        if isinstance(tags, str):
            tags = json.loads(tags)
        inp = tags.get("input_cost_per_token")
        out = tags.get("output_cost_per_token")
        if inp is None or out is None:
            continue
        try:
            inp_d = Decimal(str(inp))
            out_d = Decimal(str(out))
        except Exception:
            continue
        if inp_d <= 0 or out_d <= 0:
            continue
        provider = row.provider or "unknown"
        upstream_model = row.real_model or ""
        capability = row.capability or "chat"
        cache_create = tags.get("cache_creation_input_token_cost")
        cache_read = tags.get("cache_read_input_token_cost")
        conn.execute(
            sa.text(
                """
                INSERT INTO upstream_model_pricing (
                    provider, upstream_model, capability,
                    input_cost_per_token, output_cost_per_token,
                    cache_creation_input_token_cost, cache_read_input_token_cost,
                    effective_from, source, version
                ) VALUES (
                    :provider, :upstream_model, :capability,
                    :inp, :out, :cache_create, :cache_read,
                    :effective_from, 'toml', 1
                )
                ON CONFLICT ON CONSTRAINT uq_upstream_model_pricing_natural DO NOTHING
                """
            ),
            {
                "provider": provider,
                "upstream_model": upstream_model,
                "capability": capability,
                "inp": inp_d,
                "out": out_d,
                "cache_create": Decimal(str(cache_create)) if cache_create else None,
                "cache_read": Decimal(str(cache_read)) if cache_read else None,
                "effective_from": now,
            },
        )


def downgrade() -> None:
    op.drop_column("gateway_budgets", "budget_reset_at")
    op.drop_column("gateway_budgets", "max_parallel_requests")
    op.drop_column("gateway_budgets", "soft_limit_usd")
    op.drop_column("gateway_request_logs", "pricing_snapshot")
    op.drop_column("gateway_request_logs", "revenue_usd")
    op.drop_table("downstream_model_pricing")
    op.drop_table("upstream_model_pricing")
