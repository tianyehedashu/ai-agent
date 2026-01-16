"""fix basemodel fields for all tables

Revision ID: 006
Revises: 005
Create Date: 2026-01-15 16:00:00.000000

统一修复所有继承 BaseModel 的表，确保它们都有 created_at 和 updated_at 字段

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 所有继承 BaseModel 的表
BASEMODEL_TABLES = [
    "users",
    "agents",
    "sessions",
    "messages",
    "memories",
]


def upgrade() -> None:
    """为所有继承 BaseModel 的表统一添加缺失的字段"""

    for table_name in BASEMODEL_TABLES:
        # 为每个表添加 updated_at（如果不存在）
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table_name}' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE {table_name} ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;
        """
        )

    # messages 表特殊处理：添加 token_count 列（模型字段，但不是 BaseModel 的）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE messages ADD COLUMN token_count INTEGER;
            END IF;
        END $$;
    """
    )


def downgrade() -> None:
    """移除添加的列"""

    # 删除 messages 表的 token_count
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE messages DROP COLUMN token_count;
            END IF;
        END $$;
    """
    )

    # 删除所有表的 updated_at（仅针对那些原本没有的）
    # 注意：这里只删除 messages 表的 updated_at，因为其他表原本就有
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'updated_at'
            ) THEN
                ALTER TABLE messages DROP COLUMN updated_at;
            END IF;
        END $$;
    """
    )
