"""Drop legacy tenant_id -> gateway_teams FK on gateway tenant tables

Revision ID: 20260601_dltif
Revises: 20260531_ort
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260601_dltif"
down_revision: str | None = "20260531_ort"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_FK_TABLES = (
    "gateway_models",
    "gateway_routes",
    "gateway_alert_rules",
    "gateway_virtual_keys",
)

# PostgreSQL keeps pre-rename constraint names (team_id_fkey) after column rename.
_LEGACY_FK_NAMES = ("team_id_fkey", "tenant_id_fkey")


def _drop_tenant_team_fk(table: str) -> None:
    for name in _LEGACY_FK_NAMES:
        op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_{name}"))


def _add_tenant_team_fk(table: str) -> None:
    op.create_foreign_key(
        f"{table}_tenant_id_fkey",
        table,
        "gateway_teams",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    for table in _TENANT_FK_TABLES:
        _drop_tenant_team_fk(table)


def downgrade() -> None:
    for table in _TENANT_FK_TABLES:
        _add_tenant_team_fk(table)
