"""add_session_video_task_count

Revision ID: s3ss_v1d_cnt
Revises: v1d3o_m0d3l_dur
Create Date: 2026-02-05

为 sessions 表添加 video_task_count 字段，用于跟踪会话中的视频任务数量。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "s3ss_v1d_cnt"
down_revision: str | None = "v1d3o_m0d3l_dur"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "video_task_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="视频任务数量",
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "video_task_count")
