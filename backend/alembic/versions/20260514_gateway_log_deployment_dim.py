"""gateway_request_logs: deployment-level attribution (GatewayModel id)

Revision ID: 20260514_gld
Revises: 20260514_grlc
Create Date: 2026-05-14

- 记录 Router 实际选中的注册模型（``GatewayModel.id``）与别名快照，便于经虚拟路由进线时仍按注册行聚合用量。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260514_gld"
down_revision: str | None = "20260514_grlc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gateway_request_logs",
        sa.Column("deployment_gateway_model_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gateway_request_logs",
        sa.Column("deployment_model_name", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "ix_gateway_request_logs_deploy_team_time",
        "gateway_request_logs",
        ["team_id", "deployment_gateway_model_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gateway_request_logs_deploy_team_time",
        table_name="gateway_request_logs",
    )
    op.drop_column("gateway_request_logs", "deployment_model_name")
    op.drop_column("gateway_request_logs", "deployment_gateway_model_id")
