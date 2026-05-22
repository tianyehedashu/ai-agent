"""Add revoked_at to api_keys for disable vs revoke semantics

Revision ID: 20260604_revoked
Revises: 20260603_svac
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260604_revoked"
down_revision: str | None = "20260603_svac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="撤销时间；非空表示永久撤销，不可重新启用",
        ),
    )
    op.create_index("ix_api_keys_revoked_at", "api_keys", ["revoked_at"])
    op.execute(
        sa.text(
            """
            UPDATE api_keys
            SET revoked_at = updated_at
            WHERE is_active = false
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_revoked_at", table_name="api_keys")
    op.drop_column("api_keys", "revoked_at")
