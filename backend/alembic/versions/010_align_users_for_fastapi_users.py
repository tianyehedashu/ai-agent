"""Align users table for fastapi-users

Revision ID: 010_align_users
Revises: 009_add_agent_config_columns
Create Date: 2026-01-19

对齐 users 表以兼容 FastAPI Users:
- 添加 is_superuser 字段
- 添加 is_verified 字段
- 确保 hashed_password 字段存在（如果存password_hash 则重命名
- 确保所fastapi-users 必需字段都存
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_align_users"
down_revision: str | None = "009_add_agent_config_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """升级：添fastapi-users 必需的字""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col["name"]: col for col in inspector.get_columns("users")}

    # 1. 处理密码字段：如果存password_hash，重命名hashed_password
    if "password_hash" in columns and "hashed_password" not in columns:
        op.alter_column("users", "password_hash", new_column_name="hashed_password")
    elif "hashed_password" not in columns:
        # 如果两个都不存在，添hashed_password
        op.add_column(
            "users",
            sa.Column("hashed_password", sa.String(255), nullable=False, server_default=""),
        )

    # 2. 添加 is_superuser 字段（如果不存在
    if "is_superuser" not in columns:
        op.add_column(
            "users",
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        )

    # 3. 添加 is_verified 字段（如果不存在
    if "is_verified" not in columns:
        op.add_column(
            "users",
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        )

    # 4. 确保 is_active 字段存在（如果不存在
    if "is_active" not in columns:
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )

    # 5. 确保 email 字段存在且唯一（fastapi-users 要求
    # 检email 是否唯一
    indexes = [idx["name"] for idx in inspector.get_indexes("users")]
    if "ix_users_email" not in indexes:
        # 检查是否已有唯一约束
        constraints = [
            c["name"] for c in inspector.get_unique_constraints("users") if "email" in c["column_names"]
        ]
        if not constraints:
            op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """降级：移fastapi-users 特定字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col["name"]: col for col in inspector.get_columns("users")}

    # 1. 移除 is_verified（如果存在）
    if "is_verified" in columns:
        op.drop_column("users", "is_verified")

    # 2. 移除 is_superuser（如果存在）
    if "is_superuser" in columns:
        op.drop_column("users", "is_superuser")

    # 3. ?hashed_password 重命名回 password_hash（如果存在）
    if "hashed_password" in columns and "password_hash" not in columns:
        op.alter_column("users", "hashed_password", new_column_name="password_hash")
