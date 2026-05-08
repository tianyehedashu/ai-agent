"""add meta_prompt and generated_prompt to product_info_job_steps

Revision ID: 20260224_phase
Revises: 20260209_pi
Create Date: 2026-02-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260224_phase"
down_revision: str | None = "20260209_pi"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_info_job_steps",
        sa.Column("meta_prompt", sa.Text(), nullable=True, comment="用户编写的元提示词"),
    )
    op.add_column(
        "product_info_job_steps",
        sa.Column(
            "generated_prompt",
            sa.Text(),
            nullable=True,
            comment="Phase 1 LLM 生成的详细提示词",
        ),
    )


def downgrade() -> None:
    op.drop_column("product_info_job_steps", "generated_prompt")
    op.drop_column("product_info_job_steps", "meta_prompt")
