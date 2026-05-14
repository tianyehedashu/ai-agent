"""add last_test_reason to user_models and gateway_models

Revision ID: 20260514_mtr
Revises: 20260514_mts
Create Date: 2026-05-14

持久化上次连通性测试的人类可读原因（失败/不支持/解密错误等），成功时清空。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_mtr"
down_revision: str | None = "20260514_mts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("user_models", "gateway_models")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "last_test_reason",
                sa.Text(),
                nullable=True,
                comment="上次连通性测试说明（失败原因等）；成功时为 NULL",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "last_test_reason")
