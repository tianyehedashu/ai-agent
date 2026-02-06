"""add_video_model_duration

Revision ID: v1d3o_m0d3l_dur
Revises: a2b3c4d5e6f7
Create Date: 2026-02-05

为视频生成任务添加 model 和 duration 字段，支持选择不同的视频生成模型和时长。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v1d3o_m0d3l_dur"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 添加 model 字段
    op.add_column(
        "video_gen_tasks",
        sa.Column(
            "model",
            sa.String(50),
            nullable=False,
            server_default="openai::sora1.0",
            comment="视频生成模型: openai::sora1.0, openai::sora2.0",
        ),
    )

    # 添加 duration 字段
    op.add_column(
        "video_gen_tasks",
        sa.Column(
            "duration",
            sa.Integer(),
            nullable=False,
            server_default="5",
            comment="视频时长（秒）: sora1支持5/10/15/20, sora2支持5/10/15",
        ),
    )


def downgrade() -> None:
    op.drop_column("video_gen_tasks", "duration")
    op.drop_column("video_gen_tasks", "model")
