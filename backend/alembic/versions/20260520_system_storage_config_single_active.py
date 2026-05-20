"""one active system_storage_config row (partial unique index)

Revision ID: 20260520_ssc_uq
Revises: 20260520_ssc
Create Date: 2026-05-20

``SystemStorageConfigRepository.get_active`` 依赖「至多一条 is_active=true」；
应用层 upsert 会 deactivate 旧行，DB 层加部分唯一索引兜底并发写入。

本地/开发: ``alembic upgrade`` 执行本文件。
生产运维手工脚本（不自动执行）: alembic/sql/20260520_system_storage_config_single_active.{up,down}.sql
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260520_ssc_uq"
down_revision: str | None = "20260520_ssc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_system_storage_config_single_active"


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM system_storage_config
            WHERE is_active IS TRUE
        )
        UPDATE system_storage_config ssc
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE ssc.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
        ON system_storage_config (is_active)
        WHERE is_active IS TRUE
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
