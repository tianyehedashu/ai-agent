"""add gateway core tables and replace UserQuota

Revision ID: 20260508_gw
Revises: 20260508_pc
Create Date: 2026-05-08

新增 AI Gateway 域核心表：
- gateway_teams / gateway_team_members
- gateway_virtual_keys
- gateway_models / gateway_routes
- gateway_budgets（取代 user_quotas，并迁移数据）
- gateway_request_logs（按月分区）
- gateway_metrics_hourly（小时级聚合）
- gateway_alert_rules / gateway_alert_events

并自动为所有现有用户创建 personal team。
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260508_gw"
down_revision: str | None = "20260508_pc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_partition_for_month(table: str, year: int, month: int) -> None:
    """为分区表创建指定月份的子分区"""
    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    partition_name = f"{table}_y{year:04d}m{month:02d}"
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF {table}
        FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
        """
    )


def upgrade() -> None:
    # =========================================================================
    # 1. Teams & Members
    # =========================================================================
    op.create_table(
        "gateway_teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="shared"),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("owner_user_id", "slug", name="uq_gateway_teams_owner_slug"),
    )
    op.create_index("ix_gateway_teams_slug", "gateway_teams", ["slug"])
    op.create_index("ix_gateway_teams_owner", "gateway_teams", ["owner_user_id"])

    op.create_table(
        "gateway_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_gateway_team_members"),
    )
    op.create_index("ix_gateway_team_members_team", "gateway_team_members", ["team_id"])
    op.create_index("ix_gateway_team_members_user", "gateway_team_members", ["user_id"])

    # 为所有现有 user 创建 personal team + member
    op.execute(
        """
        WITH new_teams AS (
            INSERT INTO gateway_teams (
                id, name, slug, kind, owner_user_id, is_active,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                COALESCE(u.name, split_part(u.email, '@', 1), 'Personal'),
                'personal-' || u.id::text,
                'personal',
                u.id,
                true,
                COALESCE(u.created_at, now()),
                now()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM gateway_teams gt
                WHERE gt.owner_user_id = u.id AND gt.kind = 'personal'
            )
            RETURNING id, owner_user_id
        )
        INSERT INTO gateway_team_members (
            id, team_id, user_id, role, created_at, updated_at
        )
        SELECT gen_random_uuid(), nt.id, nt.owner_user_id, 'owner', now(), now()
        FROM new_teams nt
        """
    )

    # =========================================================================
    # 2. Virtual Keys
    # =========================================================================
    op.create_table(
        "gateway_virtual_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("key_prefix", sa.String(16), nullable=False, server_default="sk-gw-"),
        sa.Column("key_id", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("encrypted_key", sa.String(512), nullable=False),
        sa.Column(
            "allowed_models",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "allowed_capabilities",
            postgresql.ARRAY(sa.String(40)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("rpm_limit", sa.Integer, nullable=True),
        sa.Column("tpm_limit", sa.Integer, nullable=True),
        sa.Column(
            "store_full_messages",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "guardrail_enabled",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gateway_virtual_keys_team", "gateway_virtual_keys", ["team_id"])
    op.create_index("ix_gateway_virtual_keys_user", "gateway_virtual_keys", ["created_by_user_id"])
    op.create_index("ix_gateway_virtual_keys_key_id", "gateway_virtual_keys", ["key_id"])
    op.create_index("ix_gateway_virtual_keys_active", "gateway_virtual_keys", ["is_active"])
    op.create_index("ix_gateway_virtual_keys_system", "gateway_virtual_keys", ["is_system"])
    op.create_index("ix_gateway_virtual_keys_expires", "gateway_virtual_keys", ["expires_at"])

    # =========================================================================
    # 3. Gateway Models
    # =========================================================================
    op.create_table(
        "gateway_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_teams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capability", sa.String(40), nullable=False),
        sa.Column("real_model", sa.String(200), nullable=False),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("weight", sa.Integer, nullable=False, server_default="1"),
        sa.Column("rpm_limit", sa.Integer, nullable=True),
        sa.Column("tpm_limit", sa.Integer, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "name", name="uq_gateway_models_team_name"),
    )
    op.create_index("ix_gateway_models_team", "gateway_models", ["team_id"])
    op.create_index("ix_gateway_models_capability", "gateway_models", ["capability"])
    op.create_index("ix_gateway_models_credential", "gateway_models", ["credential_id"])
    op.create_index("ix_gateway_models_provider", "gateway_models", ["provider"])
    op.create_index(
        "ix_gateway_models_lookup",
        "gateway_models",
        ["team_id", "capability", "enabled"],
    )

    # =========================================================================
    # 4. Routes
    # =========================================================================
    op.create_table(
        "gateway_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_teams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("virtual_model", sa.String(200), nullable=False),
        sa.Column(
            "primary_models",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "fallbacks_general",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "fallbacks_content_policy",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "fallbacks_context_window",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "strategy",
            sa.String(40),
            nullable=False,
            server_default="simple-shuffle",
        ),
        sa.Column("retry_policy", postgresql.JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "team_id", "virtual_model", name="uq_gateway_routes_team_virtual_model"
        ),
    )
    op.create_index("ix_gateway_routes_team", "gateway_routes", ["team_id"])
    op.create_index("ix_gateway_routes_vmodel", "gateway_routes", ["virtual_model"])

    # =========================================================================
    # 5. Budgets（取代 user_quotas）
    # =========================================================================
    op.create_table(
        "gateway_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("limit_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("limit_tokens", sa.Integer, nullable=True),
        sa.Column("limit_requests", sa.Integer, nullable=True),
        sa.Column(
            "current_usd", sa.Numeric(12, 4), nullable=False, server_default="0"
        ),
        sa.Column("current_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "scope", "scope_id", "period", name="uq_gateway_budgets_scope_period"
        ),
    )
    op.create_index("ix_gateway_budgets_scope", "gateway_budgets", ["scope"])
    op.create_index("ix_gateway_budgets_scope_id", "gateway_budgets", ["scope_id"])
    op.create_index(
        "ix_gateway_budgets_lookup", "gateway_budgets", ["scope", "scope_id"]
    )

    # 数据迁移：从 user_quotas 复制
    # 检查 user_quotas 表是否存在
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "user_quotas" in insp.get_table_names():
        op.execute(
            """
            INSERT INTO gateway_budgets (
                id, scope, scope_id, period,
                limit_requests, current_requests, reset_at,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                'user',
                user_id,
                'daily',
                COALESCE(daily_text_requests, 0),
                COALESCE(current_daily_text, 0),
                daily_reset_at,
                COALESCE(created_at, now()),
                now()
            FROM user_quotas
            WHERE daily_text_requests IS NOT NULL
            ON CONFLICT (scope, scope_id, period) DO NOTHING
            """
        )
        op.execute(
            """
            INSERT INTO gateway_budgets (
                id, scope, scope_id, period,
                limit_tokens, current_tokens, reset_at,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                'user',
                user_id,
                'monthly',
                COALESCE(monthly_token_limit, 0),
                COALESCE(current_monthly_tokens, 0),
                monthly_reset_at,
                COALESCE(created_at, now()),
                now()
            FROM user_quotas
            WHERE monthly_token_limit IS NOT NULL
            ON CONFLICT (scope, scope_id, period) DO NOTHING
            """
        )

    # =========================================================================
    # 6. Request Logs（按月分区）
    # =========================================================================
    op.execute(
        """
        CREATE TABLE gateway_request_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            team_id UUID NULL,
            user_id UUID NULL,
            vkey_id UUID NULL,

            team_snapshot JSONB NULL,
            user_email_snapshot VARCHAR(255) NULL,
            vkey_name_snapshot VARCHAR(100) NULL,
            route_snapshot JSONB NULL,

            capability VARCHAR(40) NOT NULL,
            route_name VARCHAR(200) NULL,
            real_model VARCHAR(200) NULL,
            provider VARCHAR(50) NULL,

            status VARCHAR(40) NOT NULL,
            error_code VARCHAR(100) NULL,
            error_message TEXT NULL,

            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,

            latency_ms INTEGER NOT NULL DEFAULT 0,
            ttfb_ms INTEGER NULL,

            cache_hit BOOLEAN NOT NULL DEFAULT false,
            fallback_chain VARCHAR(200)[] NOT NULL DEFAULT '{}',

            request_id VARCHAR(64) NULL,
            prompt_hash VARCHAR(64) NULL,
            prompt_redacted JSONB NULL,
            response_summary JSONB NULL,
            metadata_extra JSONB NULL,

            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.create_index(
        "ix_gateway_request_logs_team_time",
        "gateway_request_logs",
        ["team_id", "created_at"],
    )
    op.create_index(
        "ix_gateway_request_logs_user_time",
        "gateway_request_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_gateway_request_logs_vkey_time",
        "gateway_request_logs",
        ["vkey_id", "created_at"],
    )
    op.create_index(
        "ix_gateway_request_logs_status_time",
        "gateway_request_logs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_gateway_request_logs_capability",
        "gateway_request_logs",
        ["capability"],
    )
    op.create_index(
        "ix_gateway_request_logs_request_id",
        "gateway_request_logs",
        ["request_id"],
    )

    # 创建当前月与下两个月的分区，确保上线即可使用
    now = datetime.now(UTC)
    for delta in (-1, 0, 1, 2):  # 上月（保险）、本月、下月、再下月
        target = (now.replace(day=1) + timedelta(days=delta * 32)).replace(day=1)
        _create_partition_for_month(
            "gateway_request_logs", target.year, target.month
        )

    # =========================================================================
    # 7. Metrics Hourly
    # =========================================================================
    op.create_table(
        "gateway_metrics_hourly",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bucket_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vkey_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("real_model", sa.String(200), nullable=True),
        sa.Column("capability", sa.String(40), nullable=True),
        sa.Column("requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "cost_usd", sa.Numeric(14, 6), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_latency_ms", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("p95_latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_hit_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "bucket_at",
            "team_id",
            "user_id",
            "vkey_id",
            "provider",
            "real_model",
            "capability",
            name="uq_gateway_metrics_hourly_dim",
        ),
    )
    op.create_index(
        "ix_gateway_metrics_hourly_bucket", "gateway_metrics_hourly", ["bucket_at"]
    )
    op.create_index(
        "ix_gateway_metrics_hourly_team_bucket",
        "gateway_metrics_hourly",
        ["team_id", "bucket_at"],
    )

    # =========================================================================
    # 8. Alert Rules / Events
    # =========================================================================
    op.create_table(
        "gateway_alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_teams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=False),
        sa.Column("window_minutes", sa.Integer, nullable=False, server_default="5"),
        sa.Column("channels", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gateway_alert_rules_team", "gateway_alert_rules", ["team_id"])
    op.create_index(
        "ix_gateway_alert_rules_lookup",
        "gateway_alert_rules",
        ["team_id", "enabled"],
    )

    op.create_table(
        "gateway_alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gateway_alert_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("notified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gateway_alert_events_rule", "gateway_alert_events", ["rule_id"])
    op.create_index("ix_gateway_alert_events_team", "gateway_alert_events", ["team_id"])


def downgrade() -> None:
    op.drop_table("gateway_alert_events")
    op.drop_table("gateway_alert_rules")
    op.drop_table("gateway_metrics_hourly")
    op.execute("DROP TABLE IF EXISTS gateway_request_logs CASCADE")
    op.drop_table("gateway_budgets")
    op.drop_table("gateway_routes")
    op.drop_table("gateway_models")
    op.drop_table("gateway_virtual_keys")
    op.drop_table("gateway_team_members")
    op.drop_table("gateway_teams")
