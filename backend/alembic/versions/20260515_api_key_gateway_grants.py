"""api key gateway grants

Revision ID: 20260515_akgg
Revises: 20260514_gld
Create Date: 2026-05-15

平台 API Key 的 ``gateway:proxy`` scope 不再天然等于“用户所属所有团队可用”。
本迁移增加 grant 表，显式绑定 API Key 可代理调用的 Gateway 团队与细粒度策略。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260515_akgg"
down_revision: str | None = "20260514_gld"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_key_gateway_grants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "allowed_models",
            postgresql.ARRAY(sa.String(length=200)),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
        sa.Column(
            "allowed_capabilities",
            postgresql.ARRAY(sa.String(length=40)),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
        sa.Column("rpm_limit", sa.Integer(), nullable=True),
        sa.Column("tpm_limit", sa.Integer(), nullable=True),
        sa.Column(
            "store_full_messages",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "guardrail_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("api_key_id", "team_id", name="uq_api_key_gateway_grants_key_team"),
    )
    op.create_index(
        "ix_api_key_gateway_grants_api_key_id", "api_key_gateway_grants", ["api_key_id"]
    )
    op.create_index("ix_api_key_gateway_grants_user_id", "api_key_gateway_grants", ["user_id"])
    op.create_index("ix_api_key_gateway_grants_team_id", "api_key_gateway_grants", ["team_id"])
    op.create_index("ix_api_key_gateway_grants_is_active", "api_key_gateway_grants", ["is_active"])
    op.create_index(
        "ix_api_key_gateway_grants_user_team",
        "api_key_gateway_grants",
        ["user_id", "team_id"],
    )
    op.execute(
        """
        INSERT INTO api_key_gateway_grants (
            api_key_id,
            user_id,
            team_id,
            allowed_models,
            allowed_capabilities,
            store_full_messages,
            guardrail_enabled,
            is_active
        )
        SELECT
            ak.id,
            ak.user_id,
            t.id,
            '{}'::character varying[],
            '{}'::character varying[],
            false,
            true,
            true
        FROM api_keys ak
        JOIN gateway_teams t
            ON t.owner_user_id = ak.user_id
           AND t.kind = 'personal'
           AND t.is_active = true
        WHERE ak.scopes @> ARRAY['gateway:proxy']::character varying[]
        ON CONFLICT ON CONSTRAINT uq_api_key_gateway_grants_key_team DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_gateway_grants_user_team", table_name="api_key_gateway_grants")
    op.drop_index("ix_api_key_gateway_grants_is_active", table_name="api_key_gateway_grants")
    op.drop_index("ix_api_key_gateway_grants_team_id", table_name="api_key_gateway_grants")
    op.drop_index("ix_api_key_gateway_grants_user_id", table_name="api_key_gateway_grants")
    op.drop_index("ix_api_key_gateway_grants_api_key_id", table_name="api_key_gateway_grants")
    op.drop_table("api_key_gateway_grants")
