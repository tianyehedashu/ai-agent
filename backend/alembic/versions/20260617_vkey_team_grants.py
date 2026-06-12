"""gateway_virtual_key_team_grants: create table + backfill self-grants

Revision ID: 20260617_vktg
Revises: 20260616_dppi
Create Date: 2026-06-17

创建跨团队聚合虚拟 Key 授权表，并为所有现存 vkey 回填自洽 grant。
顺序：建表 → 回填 → 建 partial unique index（防数据违反约束）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260617_vktg"
down_revision: str | None = "20260616_dppi"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "gateway_virtual_key_team_grants"
UQ_NAME = "uq_vkey_team_grants_active"
IX_VKEY_ACTIVE = "ix_vkey_team_grants_vkey_active"
IX_USER_TENANT_ACTIVE = "ix_vkey_team_grants_user_tenant_active"

# system vkey 的 created_by_user_id 为 NULL，回填时使用 sentinel UUID
SYSTEM_VKEY_SENTINEL_USER_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 1. 建表
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("vkey_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("granted_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_self", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. 回填自洽 grant（每个现存 active vkey 一行）
    op.execute(
        f"""
        INSERT INTO {TABLE_NAME} (id, vkey_id, tenant_id, is_active, granted_by_user_id, is_self, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            v.id,
            v.tenant_id,
            TRUE,
            COALESCE(v.created_by_user_id, '{SYSTEM_VKEY_SENTINEL_USER_ID}'::uuid),
            TRUE,
            NOW(),
            NOW()
        FROM gateway_virtual_keys v
        WHERE v.is_active = TRUE
        """
    )

    # 3. 建 partial unique index（回填后安全）
    op.execute(
        f"""
        CREATE UNIQUE INDEX {UQ_NAME}
        ON {TABLE_NAME} (vkey_id, tenant_id)
        WHERE is_active = TRUE
        """
    )

    # 4. 鉴权热路径索引
    op.execute(
        f"""
        CREATE INDEX {IX_VKEY_ACTIVE}
        ON {TABLE_NAME} (vkey_id)
        WHERE is_active = TRUE
        """
    )

    # 5. 离线清理反查索引
    op.execute(
        f"""
        CREATE INDEX {IX_USER_TENANT_ACTIVE}
        ON {TABLE_NAME} (granted_by_user_id, tenant_id)
        WHERE is_active = TRUE
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {IX_USER_TENANT_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {IX_VKEY_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {UQ_NAME}")
    op.drop_table(TABLE_NAME)
