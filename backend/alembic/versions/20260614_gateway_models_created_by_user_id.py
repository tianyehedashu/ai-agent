"""add created_by_user_id to gateway_models

Revision ID: 20260614_gmcbu
Revises: 20260613_cct
Create Date: 2026-06-14

记录团队模型的创建者，使模型创建者可以编辑自己添加的模型（即使不拥有绑定凭据）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260614_gmcbu"
down_revision: str | None = "20260613_cct"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_models",
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="创建该模型的用户 ID（refs users.id，无 DB FK）",
        ),
    )
    op.create_index(
        "ix_gateway_models_created_by_user_id",
        "gateway_models",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_models_created_by_user_id", table_name="gateway_models")
    op.drop_column("gateway_models", "created_by_user_id")
