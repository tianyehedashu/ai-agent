"""add session status and context columns

Revision ID: 005
Revises: 004
Create Date: 2026-01-14 17:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 sessions 表添加缺失的列：status, context, message_count, token_count"""

    # 添加 status 列（如果不存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                -- 先添加列（允许 NULL）
                ALTER TABLE sessions ADD COLUMN status VARCHAR(20);
                -- 从 is_active 迁移数据
                UPDATE sessions SET status = CASE
                    WHEN is_active = true THEN 'active'
                    ELSE 'archived'
                END;
                -- 设置默认值和 NOT NULL
                ALTER TABLE sessions ALTER COLUMN status SET DEFAULT 'active';
                ALTER TABLE sessions ALTER COLUMN status SET NOT NULL;
            END IF;
        END $$;
    """
    )

    # 处理 context 列：如果 metadata 存在则重命名，否则添加新列
    op.execute(
        """
        DO $$
        BEGIN
            -- 如果 metadata 列存在，重命名为 context
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'metadata'
            ) THEN
                -- 删除旧的 metadata GIN 索引（如果存在）
                DROP INDEX IF EXISTS idx_sessions_metadata_gin;
                -- 重命名 metadata 为 context
                ALTER TABLE sessions RENAME COLUMN metadata TO context;
                -- 确保默认值正确
                ALTER TABLE sessions ALTER COLUMN context SET DEFAULT '{}'::jsonb;
                -- 重新创建 context GIN 索引
                CREATE INDEX IF NOT EXISTS idx_sessions_context_gin ON sessions USING GIN (context);
            ELSIF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'context'
            ) THEN
                -- 如果 metadata 不存在且 context 也不存在，添加新列
                ALTER TABLE sessions ADD COLUMN context JSONB NOT NULL DEFAULT '{}'::jsonb;
                -- 创建 context GIN 索引
                CREATE INDEX IF NOT EXISTS idx_sessions_context_gin ON sessions USING GIN (context);
            END IF;
        END $$;
    """
    )

    # 添加 message_count 列（如果不存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'message_count'
            ) THEN
                -- 先添加列（允许 NULL）
                ALTER TABLE sessions ADD COLUMN message_count INTEGER;
                -- 计算现有消息数量
                UPDATE sessions SET message_count = (
                    SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id
                );
                -- 设置默认值和 NOT NULL
                ALTER TABLE sessions ALTER COLUMN message_count SET DEFAULT 0;
                ALTER TABLE sessions ALTER COLUMN message_count SET NOT NULL;
            END IF;
        END $$;
    """
    )

    # 添加 token_count 列（如果不存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE sessions ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
    """
    )

    # 删除旧的 is_active 列（如果存在且 status 列已创建）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'is_active'
            ) AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                -- 删除索引（如果存在）
                DROP INDEX IF EXISTS idx_sessions_active;
                -- 删除列
                ALTER TABLE sessions DROP COLUMN is_active;
            END IF;
        END $$;
    """
    )


def downgrade() -> None:
    """移除添加的列"""

    # 删除 token_count 列
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE sessions DROP COLUMN token_count;
            END IF;
        END $$;
    """
    )

    # 删除 message_count 列
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'message_count'
            ) THEN
                ALTER TABLE sessions DROP COLUMN message_count;
            END IF;
        END $$;
    """
    )

    # 删除 context 列
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'context'
            ) THEN
                ALTER TABLE sessions DROP COLUMN context;
            END IF;
        END $$;
    """
    )

    # 恢复 is_active 列（如果需要）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'is_active'
            ) THEN
                ALTER TABLE sessions ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
                -- 从 status 迁移数据
                UPDATE sessions SET is_active = (status = 'active');
            END IF;
        END $$;
    """
    )

    # 删除 status 列
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                ALTER TABLE sessions DROP COLUMN status;
            END IF;
        END $$;
    """
    )
