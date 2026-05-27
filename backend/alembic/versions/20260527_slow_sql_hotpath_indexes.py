"""慢 SQL 热路径索引：告警 job、plan lifecycle、rollup 时间窗扫描。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_slow_sql"
down_revision: str | None = "f31bf0379153"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_gateway_alert_rules_enabled",
        "gateway_alert_rules",
        ["tenant_id"],
        unique=False,
        postgresql_where=sa.text("enabled IS TRUE"),
        if_not_exists=True,
    )
    op.drop_index(
        "ix_system_gateway_alert_rules_enabled",
        table_name="system_gateway_alert_rules",
        if_exists=True,
    )
    op.create_index(
        "ix_system_gateway_alert_rules_enabled",
        "system_gateway_alert_rules",
        ["name"],
        unique=False,
        postgresql_where=sa.text("enabled IS TRUE"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_entitlement_plans_lifecycle",
        "entitlement_plans",
        ["valid_until"],
        unique=False,
        postgresql_where=sa.text("is_active IS TRUE"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_provider_plans_lifecycle",
        "provider_plans",
        ["valid_until"],
        unique=False,
        postgresql_where=sa.text("is_active IS TRUE"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_gateway_request_logs_created_at_brin",
        "gateway_request_logs",
        ["created_at"],
        unique=False,
        postgresql_using="brin",
        if_not_exists=True,
    )
    op.create_index(
        "ix_gateway_teams_active_kind_created",
        "gateway_teams",
        ["kind", "created_at"],
        unique=False,
        postgresql_where=sa.text("is_active IS TRUE"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gateway_teams_active_kind_created",
        table_name="gateway_teams",
        if_exists=True,
    )
    op.drop_index(
        "ix_gateway_request_logs_created_at_brin",
        table_name="gateway_request_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_provider_plans_lifecycle",
        table_name="provider_plans",
        if_exists=True,
    )
    op.drop_index(
        "ix_entitlement_plans_lifecycle",
        table_name="entitlement_plans",
        if_exists=True,
    )
    op.drop_index(
        "ix_system_gateway_alert_rules_enabled",
        table_name="system_gateway_alert_rules",
        if_exists=True,
    )
    op.create_index(
        "ix_system_gateway_alert_rules_enabled",
        "system_gateway_alert_rules",
        ["enabled"],
        unique=False,
        if_not_exists=True,
    )
    op.drop_index(
        "ix_gateway_alert_rules_enabled",
        table_name="gateway_alert_rules",
        if_exists=True,
    )
