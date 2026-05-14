"""one active personal team per owner_user_id (partial unique index)

Revision ID: 20260514_upt
Revises: 20260513_uvk
Create Date: 2026-05-14

``TeamRepository.get_personal`` 依赖「同一 owner 至多一条
``kind=personal AND is_active``」；仅靠 ``(owner_user_id, slug)`` 唯一无法阻止
不同 slug 的多条 personal。多行时 ``scalar_one_or_none()`` 会抛
``MultipleResultsFound``。

1. 将重复行中除最早 ``created_at``（并列则 ``id``）外全部 ``is_active=false``。
2. 创建部分唯一索引 ``UNIQUE (owner_user_id) WHERE kind='personal' AND is_active``。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260514_upt"
down_revision: str | None = "20260513_uvk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_gateway_teams_owner_personal_active"


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY owner_user_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM gateway_teams
            WHERE kind = 'personal'
              AND is_active IS TRUE
        )
        UPDATE gateway_teams gt
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE gt.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
        ON gateway_teams (owner_user_id)
        WHERE kind = 'personal' AND is_active IS TRUE
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
