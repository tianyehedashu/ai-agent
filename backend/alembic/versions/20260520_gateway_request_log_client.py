"""gateway_request_logs: client_type / client_ua for third-party client observability

Revision ID: 20260520_grlc
Revises: 20260519_drop_upc
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260520_grlc"
down_revision: str | None = "20260519_drop_upc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_request_logs",
        sa.Column("client_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "gateway_request_logs",
        sa.Column("client_ua", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "ix_gateway_request_logs_client_type",
        "gateway_request_logs",
        ["client_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_request_logs_client_type", table_name="gateway_request_logs")
    op.drop_column("gateway_request_logs", "client_ua")
    op.drop_column("gateway_request_logs", "client_type")
