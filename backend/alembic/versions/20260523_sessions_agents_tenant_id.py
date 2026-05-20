"""Phase 3b: sessions/agents add tenant_id (personal team backfill)

Revision ID: 20260523_sat
Revises: 20260522_p3
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260523_sat"
down_revision: str | None = "20260522_p3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])

    op.execute(
        """
        UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.user_id IS NOT NULL
          AND t.owner_user_id = s.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE
        """
    )

    op.execute(
        """
        UPDATE sessions s
        SET tenant_id = t.id
        FROM users u
        JOIN gateway_teams t ON t.owner_user_id = u.id
            AND t.kind = 'personal'
            AND t.is_active = TRUE
        WHERE s.anonymous_user_id IS NOT NULL
          AND s.tenant_id IS NULL
          AND u.role = 'anonymous'
          AND u.settings->>'anonymous_cookie_id' = s.anonymous_user_id
        """
    )

    op.add_column(
        "agents",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])

    op.execute(
        """
        UPDATE agents a
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE t.owner_user_id = a.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE
        """
    )
    op.execute("ALTER TABLE agents ALTER COLUMN tenant_id SET NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_agents_tenant_id", table_name="agents")
    op.drop_column("agents", "tenant_id")
    op.drop_index("ix_sessions_tenant_id", table_name="sessions")
    op.drop_column("sessions", "tenant_id")
