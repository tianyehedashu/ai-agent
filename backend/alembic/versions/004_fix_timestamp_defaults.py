"""fix timestamp defaults

Revision ID: 004
Revises: 003
Create Date: 2026-01-14 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为所有表的 created_at 和 updated_at 字段添加 server_default"""

    # 修复 users 表
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 agents 表
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 sessions 表
    op.execute(
        """
        ALTER TABLE sessions
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 messages 表（只有 created_at）
    op.execute(
        """
        ALTER TABLE messages
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 memories 表
    op.execute(
        """
        ALTER TABLE memories
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 workflows 表
    op.execute(
        """
        ALTER TABLE workflows
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )

    # 修复 workflow_versions 表（只有 created_at）
    op.execute(
        """
        ALTER TABLE workflow_versions








        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """
    )


def downgrade() -> None:
    """移除 server_default"""

    # 移除 users 表的默认值
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
    """
    )

    # 移除 agents 表的默认值
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
    """
    )

    # 移除 sessions 表的默认值
    op.execute(
        """
        ALTER TABLE sessions
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
    """
    )

    # 移除 messages 表的默认值
    op.execute(
        """
        ALTER TABLE messages
        ALTER COLUMN created_at DROP DEFAULT;
    """
    )

    # 移除 memories 表的默认值
    op.execute(
        """
        ALTER TABLE memories
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
    """
    )

    # 移除 workflows 表的默认值
    op.execute(
        """
        ALTER TABLE workflows
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
    """
    )

    # 移除 workflow_versions 表的默认值
    op.execute(
        """
        ALTER TABLE workflow_versions
        ALTER COLUMN created_at DROP DEFAULT;
    """
    )
