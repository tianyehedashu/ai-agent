"""gateway_resource_grants + request_logs.resource_owner_user_id

Revision ID: 20260701_grg
Revises: 20260630_socp
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_grg"
down_revision: str | None = "20260630_socp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS_TABLE = "gateway_resource_grants"
UQ_NAME = "uq_gateway_resource_grants_subject_target"
IX_TARGET_ENABLED = "ix_gateway_resource_grants_target_enabled"
IX_SUBJECT = "ix_gateway_resource_grants_subject"
IX_OWNER = "ix_gateway_resource_grants_owner_user_id"
IX_LOG_RESOURCE_OWNER = "ix_gateway_request_logs_resource_owner_time"


def upgrade() -> None:
    op.create_table(
        GRANTS_TABLE,
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("owner_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_kind", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_team_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("granted_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
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
            "subject_kind",
            "subject_id",
            "target_team_id",
            name=UQ_NAME,
        ),
    )
    op.create_index(IX_OWNER, GRANTS_TABLE, ["owner_user_id"])
    op.create_index(IX_SUBJECT, GRANTS_TABLE, ["subject_kind", "subject_id"])
    op.execute(
        f"""
        CREATE INDEX {IX_TARGET_ENABLED}
        ON {GRANTS_TABLE} (target_team_id, enabled)
        WHERE enabled IS TRUE
        """
    )

    op.add_column(
        "gateway_request_logs",
        sa.Column("resource_owner_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gateway_metrics_hourly",
        sa.Column("resource_owner_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        f"""
        CREATE INDEX {IX_LOG_RESOURCE_OWNER}
        ON gateway_request_logs (resource_owner_user_id, created_at)
        WHERE resource_owner_user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {IX_LOG_RESOURCE_OWNER}")
    op.drop_column("gateway_metrics_hourly", "resource_owner_user_id")
    op.drop_column("gateway_request_logs", "resource_owner_user_id")
    op.execute(f"DROP INDEX IF EXISTS {IX_TARGET_ENABLED}")
    op.drop_index(IX_SUBJECT, table_name=GRANTS_TABLE)
    op.drop_index(IX_OWNER, table_name=GRANTS_TABLE)
    op.drop_table(GRANTS_TABLE)
