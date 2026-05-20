"""Allow provider_credentials.scope NULL for tenant rows

Revision ID: 20260527_pcn
Revises: 20260526_pct
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_pcn"
down_revision: str | None = "20260526_pct"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "provider_credentials",
        "scope",
        existing_type=sa.String(20),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE provider_credentials
        SET scope = 'team'
        WHERE tenant_id IS NOT NULL AND scope IS NULL
        """
    )
    op.alter_column(
        "provider_credentials",
        "scope",
        existing_type=sa.String(20),
        nullable=False,
    )
