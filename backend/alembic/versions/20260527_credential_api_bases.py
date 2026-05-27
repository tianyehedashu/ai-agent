"""add api_bases JSONB to provider credentials

Revision ID: 20260527_api_bases
Revises: 20260526_prof
Create Date: 2026-05-27

- ``provider_credentials.api_bases`` / ``system_provider_credentials.api_bases``
- 回填 ``api_bases.openai_compat`` from legacy ``api_base``
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260527_api_bases"
down_revision: str | None = "20260526_prof"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column(
            "api_bases",
            JSONB(),
            nullable=True,
            comment="各协议 endpoint 覆盖：openai_compat / anthropic_native",
        ),
    )
    op.add_column(
        "system_provider_credentials",
        sa.Column(
            "api_bases",
            JSONB(),
            nullable=True,
            comment="各协议 endpoint 覆盖：openai_compat / anthropic_native",
        ),
    )
    op.execute(
        """
        UPDATE provider_credentials
        SET api_bases = jsonb_build_object('openai_compat', api_base)
        WHERE api_base IS NOT NULL AND trim(api_base) <> ''
        """
    )
    op.execute(
        """
        UPDATE system_provider_credentials
        SET api_bases = jsonb_build_object('openai_compat', api_base)
        WHERE api_base IS NOT NULL AND trim(api_base) <> ''
        """
    )


def downgrade() -> None:
    op.drop_column("system_provider_credentials", "api_bases")
    op.drop_column("provider_credentials", "api_bases")
