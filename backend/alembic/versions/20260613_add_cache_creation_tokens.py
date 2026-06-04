"""add cache_creation_tokens to gateway_request_logs and gateway_metrics_hourly

Revision ID: 20260613_cct
Revises: 20260612_gbt
Create Date: 2026-06-13

- gateway_request_logs 增加 cache_creation_tokens 列（分区表，PG 15+ 支持主表加列自动级联）
- gateway_metrics_hourly 增加 cache_creation_tokens 列
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_cct"
down_revision: str | None = "20260612_gbt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_request_logs",
        sa.Column(
            "cache_creation_tokens",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column(
            "cache_creation_tokens",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("gateway_request_logs", "cache_creation_tokens")
    op.drop_column("gateway_metrics_hourly", "cache_creation_tokens")
