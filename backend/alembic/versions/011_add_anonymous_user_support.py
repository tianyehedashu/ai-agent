"""Add anonymous user support to sessions

Revision ID: 011
Revises: 010_align_users_for_fastapi_users
Create Date: 2026-01-20

支持匿名用户多轮聊天- 添加 anonymous_user_id 字段sessions ?- ?user_id 改为可选（nullable?- 添加约束确保 user_id ?anonymous_user_id 至少有一个不为空
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010_align_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查列和索引是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("sessions")]
    indexes = [idx["name"] for idx in inspector.get_indexes("sessions")]

    # 1. 添加 anonymous_user_id 字段（如果不存在    if "anonymous_user_id" not in columns:
        op.add_column(
            "sessions",
            sa.Column("anonymous_user_id", sa.String(100), nullable=True),
        )

    # 2. 创建 anonymous_user_id 索引（如果不存在    if "ix_sessions_anonymous_user_id" not in indexes:
        op.create_index(
            "ix_sessions_anonymous_user_id",
            "sessions",
            ["anonymous_user_id"],
            unique=False,
        )

    # 3. ?user_id 改为可选（nullable?    # 注意：现有数据都user_id，所以这个改动是安全    op.alter_column(
        "sessions",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 4. 添加约束确保 user_id ?anonymous_user_id 至少有一个不为空
    op.create_check_constraint(
        "session_must_have_user_or_anonymous",
        "sessions",
        "(user_id IS NOT NULL) OR (anonymous_user_id IS NOT NULL)",
    )


def downgrade() -> None:
    # 1. 删除约束
    op.drop_constraint(
        "session_must_have_user_or_anonymous",
        "sessions",
        type_="check",
    )

    # 2. ?user_id 改回不可    # 注意：如果有匿名用户会话（user_id ?NULL），这个操作会失    # 需要先删除这些会话或手动处    op.alter_column(
        "sessions",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # 3. 删除 anonymous_user_id 索引
    op.drop_index("ix_sessions_anonymous_user_id", table_name="sessions")

    # 4. 删除 anonymous_user_id 字段
    op.drop_column("sessions", "anonymous_user_id")
