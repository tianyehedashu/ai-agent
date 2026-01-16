"""add memory last_accessed column

Revision ID: 007
Revises: 006
Create Date: 2026-01-15 20:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 memories 表的 last_accessed 列"""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'memories' AND column_name = 'last_accessed'
            ) THEN
                ALTER TABLE memories ADD COLUMN last_accessed
                    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END $$;
    """
    )


def downgrade() -> None:
    """移除 memories 表的 last_accessed 列"""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'memories' AND column_name = 'last_accessed'
            ) THEN
                ALTER TABLE memories DROP COLUMN last_accessed;
            END IF;
        END $$;
    """
    )
