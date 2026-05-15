"""drop provider_credentials.legacy_user_model_id

Revision ID: 20260515_drop_pc_lum
Revises: 20260515_drop_lum
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260515_drop_pc_lum"
down_revision: str | None = "20260515_drop_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE provider_credentials DROP COLUMN IF EXISTS legacy_user_model_id"
    )


def downgrade() -> None:
    pass
