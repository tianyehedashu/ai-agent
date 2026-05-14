"""drop studio workflow tables (workflows, workflow_versions)

Revision ID: 20260514_dsw
Revises: 20260514_mtr
Create Date: 2026-05-14

移除工作台（Studio）后，工作流持久化表不再使用。
upgrade：先删子表 ``workflow_versions``，再删 ``workflows``（外键顺序）。
downgrade：按 ``001_initial`` 结构恢复两表与索引。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260514_dsw"
down_revision: str | None = "20260514_mtr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("workflow_versions")
    op.drop_table("workflows")


def downgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False, default=""),
        sa.Column("config", postgresql.JSONB(), nullable=False, default=dict),
        sa.Column("is_published", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, default=dict),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
