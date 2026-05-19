"""drop legacy user_provider_configs

Revision ID: 20260519_drop_upc
Revises: 20260518_gmp
Create Date: 2026-05-19

user-scoped credentials are now stored exclusively in provider_credentials.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260519_drop_upc"
down_revision: str | None = "20260518_gmp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("provider_credentials", "legacy_user_provider_config_id")
    op.drop_table("user_provider_configs", if_exists=True)


def downgrade() -> None:
    op.create_table(
        "user_provider_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("api_base", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_provider_config"),
    )
    op.create_index(
        op.f("ix_user_provider_configs_user_id"),
        "user_provider_configs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_provider_configs_provider"),
        "user_provider_configs",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_provider_configs_is_active"),
        "user_provider_configs",
        ["is_active"],
        unique=False,
    )
    op.add_column(
        "provider_credentials",
        sa.Column(
            "legacy_user_provider_config_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="迁移自 user_provider_configs 的源记录 ID",
        ),
    )
