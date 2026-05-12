"""add provider_credentials unified table

Revision ID: 20260508_pc
Revises: a3f8c2d1e4b7
Create Date: 2026-05-08

新建 provider_credentials 表统一三处凭据存储：
- system: .env 中的全局凭据
- team: 团队共享凭据
- user: 从 user_provider_configs / user_models 迁移而来的个人凭据

保留 user_provider_configs 与 user_models 表作为兼容视图，
后续切换 use case 后再废弃。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260508_pc"
down_revision: str | None = "a3f8c2d1e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=False),
        sa.Column("api_base", sa.String(500), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "legacy_user_provider_config_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "legacy_user_model_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
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
            "scope", "scope_id", "provider", "name",
            name="uq_provider_credentials_scope_name",
        ),
    )
    op.create_index(
        "ix_provider_credentials_scope", "provider_credentials", ["scope"]
    )
    op.create_index(
        "ix_provider_credentials_scope_id", "provider_credentials", ["scope_id"]
    )
    op.create_index(
        "ix_provider_credentials_provider", "provider_credentials", ["provider"]
    )
    op.create_index(
        "ix_provider_credentials_scope_lookup",
        "provider_credentials",
        ["scope", "scope_id", "provider"],
    )

    # 数据迁移：从 user_provider_configs 复制
    op.execute(
        """
        INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, is_active, legacy_user_provider_config_id,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'user',
            user_id,
            provider,
            COALESCE(provider, 'default'),
            api_key,
            api_base,
            is_active,
            id,
            COALESCE(created_at, now()),
            COALESCE(updated_at, now())
        FROM user_provider_configs
        WHERE NOT EXISTS (
            SELECT 1 FROM provider_credentials pc
            WHERE pc.legacy_user_provider_config_id = user_provider_configs.id
        )
        """
    )

    # 数据迁移：从 user_models 复制（仅那些配置了 api_key 的）
    op.execute(
        """
        INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, is_active, legacy_user_model_id,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'user',
            user_id,
            provider,
            display_name,
            api_key_encrypted,
            api_base,
            is_active,
            id,
            COALESCE(created_at, now()),
            COALESCE(updated_at, now())
        FROM user_models
        WHERE api_key_encrypted IS NOT NULL
          AND user_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM provider_credentials pc
            WHERE pc.legacy_user_model_id = user_models.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_credentials_scope_lookup", table_name="provider_credentials"
    )
    op.drop_index(
        "ix_provider_credentials_provider", table_name="provider_credentials"
    )
    op.drop_index(
        "ix_provider_credentials_scope_id", table_name="provider_credentials"
    )
    op.drop_index(
        "ix_provider_credentials_scope", table_name="provider_credentials"
    )
    op.drop_table("provider_credentials")
