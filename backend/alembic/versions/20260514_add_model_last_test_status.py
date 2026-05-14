"""add last_test_status / last_tested_at to user_models and gateway_models

Revision ID: 20260514_mts
Revises: 20260514_upt
Create Date: 2026-05-14

为 ``user_models`` 与 ``gateway_models`` 各加两个连通性测试状态字段：

- ``last_test_status``: ``VARCHAR(20)`` nullable，取值 ``success`` / ``failed`` /
  NULL（=未测过）
- ``last_tested_at``: ``TIMESTAMPTZ`` nullable

页面"测试连接"按钮触发 ``LLMGateway.chat`` / ``embed`` 最小调用后，把结果落到
这两个字段，列表页直接展示状态徽标与上次测试时间，避免测了就丢。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_mts"
down_revision: str | None = "20260514_upt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("user_models", "gateway_models")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "last_test_status",
                sa.String(length=20),
                nullable=True,
                comment="上次连通性测试结果: success / failed / NULL=未测过",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "last_tested_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="上次连通性测试时间",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "last_tested_at")
        op.drop_column(table, "last_test_status")
