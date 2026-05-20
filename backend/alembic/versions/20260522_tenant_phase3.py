"""Phase 3: rename team_id -> tenant_id; entitlement scope -> target_* columns

Revision ID: 20260522_p3
Revises: 20260521_tds
Create Date: 2026-05-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260522_p3"
down_revision: str | None = "20260521_tds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_team_id_to_tenant_id(table: str, *, not_null: bool, drop_indexes: tuple[str, ...]) -> None:
    for idx in drop_indexes:
        op.drop_index(idx, table_name=table)
    op.execute(f"ALTER TABLE {table} RENAME COLUMN team_id TO tenant_id")
    if not_null:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL")
    op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])


def upgrade() -> None:
    # gateway_models
    op.drop_constraint("uq_gateway_models_team_name", "gateway_models", type_="unique")
    op.drop_index("ix_gateway_models_lookup", table_name="gateway_models")
    _rename_team_id_to_tenant_id(
        "gateway_models", not_null=True, drop_indexes=("ix_gateway_models_team",)
    )
    op.create_unique_constraint(
        "uq_gateway_models_tenant_name", "gateway_models", ["tenant_id", "name"]
    )
    op.create_index(
        "ix_gateway_models_lookup",
        "gateway_models",
        ["tenant_id", "capability", "enabled"],
    )

    # gateway_routes
    op.drop_constraint(
        "uq_gateway_routes_team_virtual_model", "gateway_routes", type_="unique"
    )
    _rename_team_id_to_tenant_id(
        "gateway_routes", not_null=True, drop_indexes=("ix_gateway_routes_team",)
    )
    op.create_unique_constraint(
        "uq_gateway_routes_tenant_virtual_model",
        "gateway_routes",
        ["tenant_id", "virtual_model"],
    )

    # gateway_alert_rules
    op.drop_index("ix_gateway_alert_rules_lookup", table_name="gateway_alert_rules")
    _rename_team_id_to_tenant_id(
        "gateway_alert_rules", not_null=True, drop_indexes=("ix_gateway_alert_rules_team",)
    )
    op.create_index(
        "ix_gateway_alert_rules_lookup",
        "gateway_alert_rules",
        ["tenant_id", "enabled"],
    )

    _rename_team_id_to_tenant_id(
        "gateway_alert_events",
        not_null=False,
        drop_indexes=("ix_gateway_alert_events_team",),
    )

    op.drop_index("ix_gateway_request_logs_team_time", table_name="gateway_request_logs")
    op.execute("ALTER TABLE gateway_request_logs RENAME COLUMN team_id TO tenant_id")
    op.create_index(
        "ix_gateway_request_logs_tenant_time",
        "gateway_request_logs",
        ["tenant_id", "created_at"],
    )

    op.drop_index("ix_gateway_metrics_hourly_team_bucket", table_name="gateway_metrics_hourly")
    op.execute("ALTER TABLE gateway_metrics_hourly RENAME COLUMN team_id TO tenant_id")
    op.create_index(
        "ix_gateway_metrics_hourly_tenant_bucket",
        "gateway_metrics_hourly",
        ["tenant_id", "bucket_at"],
    )

    op.drop_index("ix_api_key_gateway_grants_user_team", table_name="api_key_gateway_grants")
    op.drop_index("ix_api_key_gateway_grants_team_id", table_name="api_key_gateway_grants")
    op.execute("ALTER TABLE api_key_gateway_grants RENAME COLUMN team_id TO tenant_id")
    op.create_index(
        "ix_api_key_gateway_grants_tenant_id", "api_key_gateway_grants", ["tenant_id"]
    )
    op.create_index(
        "ix_api_key_gateway_grants_user_tenant",
        "api_key_gateway_grants",
        ["user_id", "tenant_id"],
    )
    op.drop_constraint(
        "uq_api_key_gateway_grants_key_team", "api_key_gateway_grants", type_="unique"
    )
    op.create_unique_constraint(
        "uq_api_key_gateway_grants_key_tenant",
        "api_key_gateway_grants",
        ["api_key_id", "tenant_id"],
    )

    _rename_team_id_to_tenant_id(
        "gateway_virtual_keys",
        not_null=True,
        drop_indexes=("ix_gateway_virtual_keys_team",),
    )

    # entitlement_plans: scope/scope_id -> target_kind/target_id
    op.drop_index("ix_entitlement_plans_active", table_name="entitlement_plans")
    op.execute("ALTER TABLE entitlement_plans RENAME COLUMN scope TO target_kind")
    op.execute("ALTER TABLE entitlement_plans RENAME COLUMN scope_id TO target_id")
    op.create_index(
        "ix_entitlement_plans_active",
        "entitlement_plans",
        ["target_kind", "target_id", "is_active", "valid_from", "valid_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_entitlement_plans_active", table_name="entitlement_plans")
    op.execute("ALTER TABLE entitlement_plans RENAME COLUMN target_id TO scope_id")
    op.execute("ALTER TABLE entitlement_plans RENAME COLUMN target_kind TO scope")
    op.create_index(
        "ix_entitlement_plans_active",
        "entitlement_plans",
        ["scope", "scope_id", "is_active", "valid_from", "valid_until"],
    )

    _rename_tenant_id_to_team_id("gateway_virtual_keys", not_null=True)

    for table in (
        "api_key_gateway_grants",
        "gateway_metrics_hourly",
        "gateway_request_logs",
        "gateway_alert_events",
    ):
        _rename_tenant_id_to_team_id(table, not_null=False)

    op.drop_index("ix_gateway_alert_rules_lookup", table_name="gateway_alert_rules")
    _rename_tenant_id_to_team_id("gateway_alert_rules", not_null=True)
    op.create_index(
        "ix_gateway_alert_rules_lookup",
        "gateway_alert_rules",
        ["team_id", "enabled"],
    )

    op.drop_constraint(
        "uq_gateway_routes_tenant_virtual_model", "gateway_routes", type_="unique"
    )
    _rename_tenant_id_to_team_id("gateway_routes", not_null=True)
    op.create_unique_constraint(
        "uq_gateway_routes_team_virtual_model",
        "gateway_routes",
        ["team_id", "virtual_model"],
    )

    op.drop_index("ix_gateway_models_lookup", table_name="gateway_models")
    op.drop_constraint("uq_gateway_models_tenant_name", "gateway_models", type_="unique")
    _rename_tenant_id_to_team_id("gateway_models", not_null=True)
    op.create_unique_constraint(
        "uq_gateway_models_team_name", "gateway_models", ["team_id", "name"]
    )
    op.create_index(
        "ix_gateway_models_lookup",
        "gateway_models",
        ["team_id", "capability", "enabled"],
    )


def _rename_tenant_id_to_team_id(table: str, *, not_null: bool) -> None:
    op.drop_index(f"ix_{table}_tenant", table_name=table)
    op.execute(f"ALTER TABLE {table} RENAME COLUMN tenant_id TO team_id")
    if not_null:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN team_id DROP NOT NULL")
    op.create_index(f"ix_{table}_team", table, ["team_id"])
