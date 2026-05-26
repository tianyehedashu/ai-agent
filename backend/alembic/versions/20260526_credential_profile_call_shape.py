"""add profile_id to credentials and upstream_call_shape to gateway models

Revision ID: 20260526_prof
Revises: 20260605_sys_cred_models
Create Date: 2026-05-26

- ``provider_credentials.profile_id`` / ``system_provider_credentials.profile_id``
- ``gateway_models.upstream_call_shape`` / ``system_gateway_models.upstream_call_shape``
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_prof"
down_revision: str | None = "20260605_sys_cred_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column(
            "profile_id",
            sa.String(length=64),
            nullable=True,
            comment="上游方案 ID（如 volcengine.coding_plan）；NULL 表示 provider.default",
        ),
    )
    op.add_column(
        "system_provider_credentials",
        sa.Column(
            "profile_id",
            sa.String(length=64),
            nullable=True,
            comment="上游方案 ID；NULL 表示 provider.default",
        ),
    )
    op.add_column(
        "gateway_models",
        sa.Column(
            "upstream_call_shape",
            sa.String(length=32),
            nullable=True,
            comment="出站 LiteLLM 调用形：openai_compat / anthropic_native",
        ),
    )
    op.add_column(
        "system_gateway_models",
        sa.Column(
            "upstream_call_shape",
            sa.String(length=32),
            nullable=True,
            comment="出站 LiteLLM 调用形：openai_compat / anthropic_native",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_gateway_models", "upstream_call_shape")
    op.drop_column("gateway_models", "upstream_call_shape")
    op.drop_column("system_provider_credentials", "profile_id")
    op.drop_column("provider_credentials", "profile_id")
