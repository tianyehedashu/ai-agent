"""tenant data scope: system_* tables and migrate global gateway rows

Revision ID: 20260521_tds
Revises: 20260520_ssc_uq
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_tds"
down_revision: str | None = "20260520_ssc_uq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_gateway_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capability", sa.String(40), nullable=False),
        sa.Column("real_model", sa.String(200), nullable=False),
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("weight", sa.Integer(), server_default="1", nullable=False),
        sa.Column("rpm_limit", sa.Integer(), nullable=True),
        sa.Column("tpm_limit", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_test_status", sa.String(20), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_system_gateway_models_name"),
    )
    op.create_index(
        "ix_system_gateway_models_lookup",
        "system_gateway_models",
        ["capability", "enabled"],
    )

    op.execute(
        """
        INSERT INTO system_gateway_models (
            id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        )
        SELECT DISTINCT ON (name)
            id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        FROM gateway_models
        WHERE team_id IS NULL
        ORDER BY name, updated_at DESC NULLS LAST, id
        """
    )
    op.execute("DELETE FROM gateway_models WHERE team_id IS NULL")

    op.create_table(
        "system_gateway_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("virtual_model", sa.String(200), nullable=False),
        sa.Column("primary_models", postgresql.ARRAY(sa.String(200)), nullable=False),
        sa.Column("fallbacks_general", postgresql.ARRAY(sa.String(200)), nullable=False),
        sa.Column("fallbacks_content_policy", postgresql.ARRAY(sa.String(200)), nullable=False),
        sa.Column("fallbacks_context_window", postgresql.ARRAY(sa.String(200)), nullable=False),
        sa.Column("strategy", sa.String(40), server_default="simple-shuffle", nullable=False),
        sa.Column("retry_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("virtual_model", name="uq_system_gateway_routes_virtual_model"),
    )
    op.execute(
        """
        INSERT INTO system_gateway_routes (
            id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        )
        SELECT DISTINCT ON (virtual_model)
            id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        FROM gateway_routes
        WHERE team_id IS NULL
        ORDER BY virtual_model, updated_at DESC NULLS LAST, id
        """
    )
    op.execute("DELETE FROM gateway_routes WHERE team_id IS NULL")

    op.create_table(
        "system_gateway_alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=False),
        sa.Column("window_minutes", sa.Integer(), server_default="5", nullable=False),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO system_gateway_alert_rules (
            id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        )
        SELECT
            id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        FROM gateway_alert_rules
        WHERE team_id IS NULL
        """
    )
    op.execute("DELETE FROM gateway_alert_rules WHERE team_id IS NULL")

    op.create_table(
        "system_provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("api_base", sa.String(500), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "name", name="uq_system_provider_credentials_provider_name"
        ),
    )
    op.execute(
        """
        INSERT INTO system_provider_credentials (
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        )
        SELECT DISTINCT ON (provider, name)
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        FROM provider_credentials
        WHERE scope = 'system'
        ORDER BY provider, name, updated_at DESC NULLS LAST, id
        """
    )
    op.execute(
        """
        DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (
            SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM system_gateway_models sgm WHERE sgm.credential_id = pc.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO gateway_models (
            id, team_id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        )
        SELECT
            id, NULL, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        FROM system_gateway_models
        """
    )
    op.drop_table("system_gateway_models")

    op.execute(
        """
        INSERT INTO gateway_routes (
            id, team_id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        )
        SELECT
            id, NULL, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        FROM system_gateway_routes
        """
    )
    op.drop_table("system_gateway_routes")

    op.execute(
        """
        INSERT INTO gateway_alert_rules (
            id, team_id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        )
        SELECT
            id, NULL, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        FROM system_gateway_alert_rules
        """
    )
    op.drop_table("system_gateway_alert_rules")

    op.execute(
        """
        INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        )
        SELECT
            id, 'system', NULL, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        FROM system_provider_credentials
        """
    )
    op.drop_table("system_provider_credentials")
