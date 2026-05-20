"""Phase 3e: provider_credentials team scope → tenant_id

Revision ID: 20260526_pct
Revises: 20260525_dso
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260526_pct"
down_revision: str | None = "20260525_dso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_provider_credentials_tenant_id", "provider_credentials", ["tenant_id"])

    op.execute(
        """
        UPDATE provider_credentials
        SET tenant_id = scope_id
        WHERE scope = 'team' AND scope_id IS NOT NULL
        """
    )
    op.execute(
        """
        DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id)
          AND NOT EXISTS (
              SELECT 1 FROM system_gateway_models sgm WHERE sgm.credential_id = pc.id
          )
        """
    )
    op.execute(
        """
        UPDATE provider_credentials
        SET scope = NULL, scope_id = NULL
        WHERE scope = 'team'
        """
    )

    op.drop_constraint("uq_provider_credentials_scope_name", "provider_credentials", type_="unique")
    op.create_index(
        "uq_provider_credentials_tenant_provider_name",
        "provider_credentials",
        ["tenant_id", "provider", "name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_provider_credentials_user_scope_name",
        "provider_credentials",
        ["scope", "scope_id", "provider", "name"],
        unique=True,
        postgresql_where=sa.text("scope = 'user'"),
    )


def downgrade() -> None:
    op.drop_index("uq_provider_credentials_user_scope_name", table_name="provider_credentials")
    op.drop_index("uq_provider_credentials_tenant_provider_name", table_name="provider_credentials")
    op.execute(
        """
        UPDATE provider_credentials
        SET scope = 'team', scope_id = tenant_id
        WHERE tenant_id IS NOT NULL AND scope IS NULL
        """
    )
    op.drop_index("ix_provider_credentials_tenant_id", table_name="provider_credentials")
    op.drop_column("provider_credentials", "tenant_id")
    op.create_unique_constraint(
        "uq_provider_credentials_scope_name",
        "provider_credentials",
        ["scope", "scope_id", "provider", "name"],
    )
