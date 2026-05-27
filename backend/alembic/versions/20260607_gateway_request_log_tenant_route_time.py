"""Add tenant + route_name + created_at index on gateway_request_logs.

Revision ID: 20260607_tenant_route
Revises: 20260606_anon_tenant
Create Date: 2026-06-07

Speeds up model usage-summary aggregation (route_name IN (...) + tenant + time window).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260607_tenant_route"
down_revision: str | None = "20260606_anon_tenant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_gateway_request_logs_tenant_route_time",
        "gateway_request_logs",
        ["tenant_id", "route_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gateway_request_logs_tenant_route_time",
        table_name="gateway_request_logs",
    )
