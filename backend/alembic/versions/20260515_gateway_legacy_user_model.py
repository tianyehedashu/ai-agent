"""gateway_models.legacy_user_model_id（占位 revision，列由 drop_lum 清理）

Revision ID: 20260515_gm_lum
Revises: 20260515_akgg
Create Date: 2026-05-15
"""

from collections.abc import Sequence

revision: str = "20260515_gm_lum"
down_revision: str | None = "20260515_akgg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """历史环境可能已加列；新环境由 drop_lum 幂等清理，此处不再 ADD。"""


def downgrade() -> None:
    pass
