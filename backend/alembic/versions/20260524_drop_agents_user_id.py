"""Phase 3c: drop agents.user_id (tenant_id is authoritative)

Revision ID: 20260524_dau
Revises: 20260523_sat
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260524_dau"
down_revision: str | None = "20260523_sat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_constraint("agents_user_id_fkey", "agents", type_="foreignkey")
    op.drop_column("agents", "user_id")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE agents a
        SET user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE a.tenant_id = t.id
          AND t.kind = 'personal'
          AND t.owner_user_id IS NOT NULL
        """
    )
    op.execute("ALTER TABLE agents ALTER COLUMN user_id SET NOT NULL")
    op.create_foreign_key(
        "agents_user_id_fkey",
        "agents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])
