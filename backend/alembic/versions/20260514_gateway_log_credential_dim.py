"""gateway_request_logs + gateway_metrics_hourly: credential attribution

Revision ID: 20260514_grlc
Revises: 20260514_gbm
Create Date: 2026-05-14

- 请求日志增加 ``credential_id`` / ``credential_name_snapshot``（可空，兼容历史）
- 小时 rollup 唯一维度增加 ``credential_id``（PostgreSQL 唯一索引允许多条 NULL）
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260514_grlc"
down_revision: str | None = "20260514_gbm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_request_logs",
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gateway_request_logs",
        sa.Column("credential_name_snapshot", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_gateway_request_logs_credential_time",
        "gateway_request_logs",
        ["credential_id", "created_at"],
    )

    op.add_column(
        "gateway_metrics_hourly",
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.drop_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "team_id",
            "user_id",
            "vkey_id",
            "credential_id",
            "provider",
            "real_model",
            "capability",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_gateway_metrics_hourly_dim",
        "gateway_metrics_hourly",
        [
            "bucket_at",
            "team_id",
            "user_id",
            "vkey_id",
            "provider",
            "real_model",
            "capability",
        ],
    )
    op.drop_column("gateway_metrics_hourly", "credential_id")

    op.drop_index("ix_gateway_request_logs_credential_time", table_name="gateway_request_logs")
    op.drop_column("gateway_request_logs", "credential_name_snapshot")
    op.drop_column("gateway_request_logs", "credential_id")
