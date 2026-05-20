"""Phase 3d: sessions tenant_id NOT NULL; drop user_id / anonymous_user_id

Revision ID: 20260525_dso
Revises: 20260524_dau
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260525_dso"
down_revision: str | None = "20260524_dau"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.user_id IS NOT NULL
          AND s.tenant_id IS NULL
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
    op.execute(
        """
        INSERT INTO gateway_teams (
            id, name, slug, kind, owner_user_id, settings, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'Personal',
            'personal-' || u.user_id::text,
            'personal',
            u.user_id,
            '{}'::jsonb,
            TRUE,
            NOW(),
            NOW()
        FROM (SELECT DISTINCT user_id FROM sessions WHERE tenant_id IS NULL AND user_id IS NOT NULL) u
        WHERE NOT EXISTS (
            SELECT 1 FROM gateway_teams t
            WHERE t.owner_user_id = u.user_id AND t.kind = 'personal' AND t.is_active = TRUE
        )
        """
    )
    op.execute(
        """
        INSERT INTO gateway_team_members (id, team_id, user_id, role, created_at, updated_at)
        SELECT gen_random_uuid(), t.id, t.owner_user_id, 'owner', NOW(), NOW()
        FROM gateway_teams t
        WHERE t.kind = 'personal'
          AND NOT EXISTS (
              SELECT 1 FROM gateway_team_members m
              WHERE m.team_id = t.id AND m.user_id = t.owner_user_id
          )
        """
    )
    op.execute(
        """
        UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.tenant_id IS NULL
          AND s.user_id IS NOT NULL
          AND t.owner_user_id = s.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE
        """
    )
    op.execute("DELETE FROM sessions WHERE tenant_id IS NULL")
    op.execute("ALTER TABLE sessions ALTER COLUMN tenant_id SET NOT NULL")

    op.drop_constraint("session_must_have_user_or_anonymous", "sessions", type_="check")
    op.drop_index("ix_sessions_anonymous_user_id", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_constraint("sessions_user_id_fkey", "sessions", type_="foreignkey")
    op.drop_column("sessions", "anonymous_user_id")
    op.drop_column("sessions", "user_id")


def downgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("anonymous_user_id", sa.String(100), nullable=True),
    )
    op.execute(
        """
        UPDATE sessions s
        SET user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE s.tenant_id = t.id
          AND t.kind = 'personal'
          AND t.owner_user_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM users u
              WHERE u.id = t.owner_user_id AND u.role <> 'anonymous'
          )
        """
    )
    op.execute(
        """
        UPDATE sessions s
        SET user_id = NULL,
            anonymous_user_id = u.settings->>'anonymous_cookie_id'
        FROM gateway_teams t
        JOIN users u ON u.id = t.owner_user_id
        WHERE s.tenant_id = t.id
          AND t.kind = 'personal'
          AND u.role = 'anonymous'
          AND s.user_id IS NULL
        """
    )
    op.create_foreign_key(
        "sessions_user_id_fkey",
        "sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_anonymous_user_id", "sessions", ["anonymous_user_id"])
    op.create_check_constraint(
        "session_must_have_user_or_anonymous",
        "sessions",
        "(user_id IS NOT NULL) OR (anonymous_user_id IS NOT NULL)",
    )
    op.alter_column("sessions", "tenant_id", nullable=True)
