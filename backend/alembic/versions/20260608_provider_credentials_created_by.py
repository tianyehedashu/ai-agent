"""provider_credentials.created_by_user_id for member-private team credentials."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260608_cred_creator"
down_revision: str | None = "20260527_slow_sql"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Team-scope credential creator; NULL = legacy shared admin-managed",
        ),
    )
    op.create_index(
        "ix_provider_credentials_tenant_creator",
        "provider_credentials",
        ["tenant_id", "created_by_user_id"],
        unique=False,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_credentials_tenant_creator",
        table_name="provider_credentials",
    )
    op.drop_column("provider_credentials", "created_by_user_id")
