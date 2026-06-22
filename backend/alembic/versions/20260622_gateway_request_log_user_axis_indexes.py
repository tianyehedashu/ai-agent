"""Partial indexes for gateway_request_logs user-axis visibility queries.

Revision ID: 20260622_grl_user_ix
Revises: 20260622_btcc
Create Date: 2026-06-22

Speeds up usage_aggregation=user list/count by matching split disjuncts:
- platform inbound: user_id + created_at WHERE vkey_id IS NULL
- vkey attributed: vkey_id + created_at WHERE vkey_id IS NOT NULL
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260622_grl_user_ix"
down_revision: str | None = "20260622_btcc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_gateway_request_logs_user_platform_inbound",
        "gateway_request_logs",
        ["user_id", "created_at"],
        postgresql_where="vkey_id IS NULL",
    )
    op.create_index(
        "ix_gateway_request_logs_vkey_time_notnull",
        "gateway_request_logs",
        ["vkey_id", "created_at"],
        postgresql_where="vkey_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gateway_request_logs_vkey_time_notnull",
        table_name="gateway_request_logs",
    )
    op.drop_index(
        "ix_gateway_request_logs_user_platform_inbound",
        table_name="gateway_request_logs",
    )
