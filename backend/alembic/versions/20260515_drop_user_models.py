"""drop user_models table

Revision ID: 20260515_drop_um
Revises: 20260515_um_data
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260515_drop_um"
down_revision: str | None = "20260515_um_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("user_models")


def downgrade() -> None:
    raise NotImplementedError("user_models 表已废弃，不支持回滚")
