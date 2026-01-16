"""add performance indexes

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 复合索引优化常见查询
    op.create_index(
        "idx_sessions_user_created",
        "sessions",
        ["user_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index(
        "idx_messages_session_created",
        "messages",
        ["session_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index("idx_memories_user_type", "memories", ["user_id", "memory_type"], unique=False)

    op.create_index(
        "idx_memories_user_importance",
        "memories",
        ["user_id", "importance", "updated_at"],
        unique=False,
        postgresql_ops={"importance": "DESC", "updated_at": "DESC"},
    )

    # 部分索引（仅索引活跃数据）
    op.execute(
        """
        CREATE INDEX idx_sessions_active
        ON sessions(user_id, created_at DESC)
        WHERE is_active = true
    """
    )

    # GIN 索引用于 JSONB 查询
    op.execute(
        """
        CREATE INDEX idx_agents_config_gin
        ON agents USING GIN (config)
    """
    )

    op.execute(
        """
        CREATE INDEX idx_sessions_metadata_gin
        ON sessions USING GIN (metadata)
    """
    )


def downgrade() -> None:
    op.drop_index("idx_sessions_user_created", table_name="sessions")
    op.drop_index("idx_messages_session_created", table_name="messages")
    op.drop_index("idx_memories_user_type", table_name="memories")
    op.drop_index("idx_memories_user_importance", table_name="memories")
    op.execute("DROP INDEX IF EXISTS idx_sessions_active")
    op.execute("DROP INDEX IF EXISTS idx_agents_config_gin")
    op.execute("DROP INDEX IF EXISTS idx_sessions_metadata_gin")
