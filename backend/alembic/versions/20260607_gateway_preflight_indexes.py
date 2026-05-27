"""Gateway 预检热路径复合索引补充。"""

from alembic import op

revision = "20260607_gw_pref_idx"
down_revision = "20260606_anon_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_system_gateway_grants_target_enabled",
        "system_gateway_grants",
        ["target_kind", "target_id"],
        unique=False,
        postgresql_where="enabled IS TRUE",
        if_not_exists=True,
    )
    op.create_index(
        "ix_gateway_routes_tenant_virtual_enabled",
        "gateway_routes",
        ["tenant_id", "virtual_model"],
        unique=False,
        postgresql_where="enabled IS TRUE",
        if_not_exists=True,
    )
    op.create_index(
        "ix_gateway_budgets_plan_lookup",
        "gateway_budgets",
        ["target_kind", "target_id", "period", "model_name"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_budgets_plan_lookup", table_name="gateway_budgets", if_exists=True)
    op.drop_index(
        "ix_gateway_routes_tenant_virtual_enabled",
        table_name="gateway_routes",
        if_exists=True,
    )
    op.drop_index(
        "ix_system_gateway_grants_target_enabled",
        table_name="system_gateway_grants",
        if_exists=True,
    )
