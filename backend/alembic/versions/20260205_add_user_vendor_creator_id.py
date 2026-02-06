"""Add vendor_creator_id to users table

Revision ID: 20260205_vendor_id
Revises: s3ss_v1d_cnt
Create Date: 2026-02-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260205_vendor_id"
down_revision: str | None = "s3ss_v1d_cnt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "vendor_creator_id",
            sa.Integer(),
            nullable=True,
            comment="厂商系统操作用户 ID（如 GIIKIN creator_id）",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "vendor_creator_id")
