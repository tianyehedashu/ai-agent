"""downstream_model_pricing.scope: team -> tenant

Revision ID: 20260530_dps_tenant
Revises: 20260529_gbrt
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260530_dps_tenant"
down_revision: str | None = "20260529_gbrt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE downstream_model_pricing
        SET scope = 'tenant'
        WHERE scope = 'team'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE downstream_model_pricing
        SET scope = 'team'
        WHERE scope = 'tenant'
        """
    )
