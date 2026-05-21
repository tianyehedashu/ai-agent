"""Drop all DB FOREIGN KEY constraints in public schema

Revision ID: 20260602_dafk
Revises: 20260601_dltif
Create Date: 2026-06-02

Application layer owns referential integrity (no DB FK project-wide).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260602_dafk"
down_revision: str | None = "20260601_dltif"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_ALL_PUBLIC_FKS = """
DO $drop_all_public_fks$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT n.nspname AS schemaname, t.relname AS tablename, c.conname AS conname
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE c.contype = 'f'
          AND n.nspname = 'public'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
            r.schemaname,
            r.tablename,
            r.conname
        );
    END LOOP;
END $drop_all_public_fks$;
"""


def upgrade() -> None:
    op.execute(sa.text(_DROP_ALL_PUBLIC_FKS))


def downgrade() -> None:
    # Intentionally empty: restoring dozens of FK definitions is environment-specific.
    # Use a DB backup or hand-written down.sql if rollback is required.
    pass
