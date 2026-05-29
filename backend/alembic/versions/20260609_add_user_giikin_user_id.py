"""Add giikin_user_id to users table

Revision ID: 20260609_giikin_uid
Revises: 20260608_cred_creator
Create Date: 2026-06-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260609_giikin_uid"
down_revision: str | None = "20260608_cred_creator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "giikin_user_id",
            sa.String(length=64),
            nullable=True,
            comment="giikin 单点登录用户 ID（SSO 模式下经 HiGress 注入，JIT 映射键）",
        ),
    )
    op.create_index(
        "ix_users_giikin_user_id",
        "users",
        ["giikin_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_giikin_user_id", table_name="users")
    op.drop_column("users", "giikin_user_id")
