"""add_video_gen_tasks

Revision ID: v1d3o_g3n_t4sk
Revises: 20260129_seed_default_mcp_prompts
Create Date: 2026-02-02

视频生成任务表：存储视频生成任务的状态、提示词和结果
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "v1d3o_g3n_t4sk"
down_revision: str | None = "r0s1t2u3v4w5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_gen_tasks",
        # ID
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        # 所有权字段
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "anonymous_user_id",
            sa.String(100),
            nullable=True,
            comment="匿名用户ID，用于未登录用户的任务",
        ),
        # 关联会话
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
            comment="关联的会话ID",
        ),
        # 厂商任务标识
        sa.Column(
            "workflow_id",
            sa.String(100),
            nullable=True,
            comment="厂商返回的 workflow_id",
        ),
        sa.Column(
            "run_id",
            sa.String(100),
            nullable=True,
            comment="厂商返回的 run_id",
        ),
        # 任务状态
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="任务状态: pending, running, completed, failed, cancelled",
        ),
        # 提示词相关
        sa.Column(
            "prompt_text",
            sa.Text(),
            nullable=True,
            comment="完整的视频生成提示词",
        ),
        sa.Column(
            "prompt_source",
            sa.String(50),
            nullable=True,
            comment="提示词来源: agent_generated, user_provided, template",
        ),
        # 参考图片与站点
        sa.Column(
            "reference_images",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="参考图片 URL 列表",
        ),
        sa.Column(
            "marketplace",
            sa.String(10),
            nullable=False,
            server_default="jp",
            comment="目标站点: jp, us, de, uk, fr, it, es 等",
        ),
        # 结果
        sa.Column(
            "result",
            JSONB,
            nullable=True,
            comment="厂商返回的完整结果（含 video_url 等）",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="错误信息",
        ),
        # 时间戳
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 创建索引
    op.create_index("ix_video_gen_tasks_user_id", "video_gen_tasks", ["user_id"])
    op.create_index(
        "ix_video_gen_tasks_anonymous_user_id", "video_gen_tasks", ["anonymous_user_id"]
    )
    op.create_index("ix_video_gen_tasks_session_id", "video_gen_tasks", ["session_id"])
    op.create_index("ix_video_gen_tasks_workflow_id", "video_gen_tasks", ["workflow_id"])
    op.create_index("ix_video_gen_tasks_run_id", "video_gen_tasks", ["run_id"])
    op.create_index("ix_video_gen_tasks_status", "video_gen_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("video_gen_tasks")
