"""fix user schema

Revision ID: 003
Revises: 002
Create Date: 2026-01-14 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 检查并重命名 avatar 列为 avatar_url（如果存在）
    # 使用 PostgreSQL 的 ALTER TABLE ... RENAME COLUMN（如果列存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'avatar'
            ) THEN
                ALTER TABLE users RENAME COLUMN avatar TO avatar_url;
            END IF;
        END $$;
    """
    )

    # 如果 avatar_url 列不存在，则添加它
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'avatar_url'
            ) THEN
                ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);
            END IF;
        END $$;
    """
    )

    # 添加 settings 列（如果不存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'settings'
            ) THEN
                ALTER TABLE users ADD COLUMN settings JSONB NOT NULL DEFAULT '{}'::jsonb;
            END IF;
        END $$;
    """
    )

    # 添加 status 列（如果不存在）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'status'
            ) THEN
                ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
            END IF;
        END $$;
    """
    )

    # 修改 name 列为可空（如果当前不可空）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'name'
                AND is_nullable = 'NO'
            ) THEN
                ALTER TABLE users ALTER COLUMN name DROP NOT NULL;
            END IF;
        END $$;
    """
    )


def downgrade() -> None:
    # 恢复 name 列为不可空（如果需要）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'name'
                AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE users ALTER COLUMN name SET NOT NULL;
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
                WHERE table_name = 'users' AND column_name = 'status'
            ) THEN
                ALTER TABLE users DROP COLUMN status;
            END IF;
        END $$;
    """
    )

    # 删除 settings 列
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'settings'
            ) THEN
                ALTER TABLE users DROP COLUMN settings;
            END IF;
        END $$;
    """
    )

    # 将 avatar_url 重命名回 avatar
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'avatar_url'
            ) THEN
                ALTER TABLE users RENAME COLUMN avatar_url TO avatar;
            END IF;
        END $$;
    """
    )
