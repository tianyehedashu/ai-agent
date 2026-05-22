"""System gateway visibility columns and grants ACL table

Revision ID: 20260603_svac
Revises: 20260602_dafk
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260603_svac"
down_revision: str | None = "20260602_dafk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "system_provider_credentials",
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=False,
            server_default="public",
        ),
    )
    op.add_column(
        "system_gateway_models",
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=False,
            server_default="inherit",
        ),
    )
    op.create_table(
        "system_gateway_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("subject_kind", sa.String(length=20), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_kind", sa.String(length=20), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_kind",
            "subject_id",
            "target_kind",
            "target_id",
            name="uq_system_gateway_grants_subject_target",
        ),
    )
    op.create_index(
        "ix_system_gateway_grants_subject",
        "system_gateway_grants",
        ["subject_kind", "subject_id"],
    )
    op.create_index(
        "ix_system_gateway_grants_target",
        "system_gateway_grants",
        ["target_kind", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_system_gateway_grants_target", table_name="system_gateway_grants")
    op.drop_index("ix_system_gateway_grants_subject", table_name="system_gateway_grants")
    op.drop_table("system_gateway_grants")
    op.drop_column("system_gateway_models", "visibility")
    op.drop_column("system_provider_credentials", "visibility")
