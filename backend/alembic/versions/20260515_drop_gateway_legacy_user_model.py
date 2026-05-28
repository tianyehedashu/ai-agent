"""drop gateway_models.legacy_user_model_id

Revision ID: 20260515_drop_lum
Revises: 20260515_drop_um
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260515_drop_lum"
down_revision: str | None = "20260515_drop_um"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gateway_models_legacy_user_model_id")
    op.execute("ALTER TABLE gateway_models DROP COLUMN IF EXISTS legacy_user_model_id")


def downgrade() -> None:
    pass
