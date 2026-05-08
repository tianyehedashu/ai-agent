"""add product_info tables

Revision ID: 20260209_pi
Revises: 20260205_vendor_id
Create Date: 2026-02-09

产品信息工作流表：jobs, steps, prompt_templates, image_gen_tasks
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260209_pi"
down_revision: str | None = "20260205_vendor_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_info_jobs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
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
            comment="匿名用户ID",
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
            comment="关联会话ID",
        ),
        sa.Column("title", sa.String(200), nullable=True, comment="任务标题"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="draft, running, completed, failed, partial",
        ),
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
    op.create_index("ix_product_info_jobs_user_id", "product_info_jobs", ["user_id"])
    op.create_index(
        "ix_product_info_jobs_anonymous_user_id",
        "product_info_jobs",
        ["anonymous_user_id"],
    )
    op.create_index("ix_product_info_jobs_session_id", "product_info_jobs", ["session_id"])
    op.create_index("ix_product_info_jobs_status", "product_info_jobs", ["status"])

    op.create_table(
        "product_info_job_steps",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_info_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="步骤顺序 1,2,3..."),
        sa.Column(
            "capability_id",
            sa.String(50),
            nullable=False,
            comment="image_analysis, product_link_analysis, ...",
        ),
        sa.Column(
            "input_snapshot",
            JSONB,
            nullable=True,
            comment="本次执行时的完整输入",
        ),
        sa.Column(
            "output_snapshot",
            JSONB,
            nullable=True,
            comment="本步执行结果",
        ),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column(
            "prompt_template_id",
            UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index("ix_product_info_job_steps_job_id", "product_info_job_steps", ["job_id"])
    op.create_index(
        "ix_product_info_job_steps_capability_id", "product_info_job_steps", ["capability_id"]
    )
    op.create_index("ix_product_info_job_steps_status", "product_info_job_steps", ["status"])

    op.create_table(
        "product_info_prompt_templates",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("anonymous_user_id", sa.String(100), nullable=True),
        sa.Column(
            "capability_id",
            sa.String(50),
            nullable=False,
            comment="image_analysis, ...",
        ),
        sa.Column("name", sa.String(100), nullable=False, comment="模板名称"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("prompts", JSONB, nullable=True, comment="8 条提示词，仅 image_gen_prompts 用"),
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
    op.create_index(
        "ix_product_info_prompt_templates_user_id",
        "product_info_prompt_templates",
        ["user_id"],
    )
    op.create_index(
        "ix_product_info_prompt_templates_anonymous_user_id",
        "product_info_prompt_templates",
        ["anonymous_user_id"],
    )
    op.create_index(
        "ix_product_info_prompt_templates_capability_id",
        "product_info_prompt_templates",
        ["capability_id"],
    )

    op.create_table(
        "product_image_gen_tasks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("anonymous_user_id", sa.String(100), nullable=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_info_jobs.id", ondelete="SET NULL"),
            nullable=True,
            comment="关联的产品信息任务",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "prompts",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="8 条 { slot, prompt, model?, size? }",
        ),
        sa.Column(
            "result_images",
            JSONB,
            nullable=True,
            comment="8 条 { slot, url }",
        ),
        sa.Column("error_message", sa.String(500), nullable=True),
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
    op.create_index("ix_product_image_gen_tasks_user_id", "product_image_gen_tasks", ["user_id"])
    op.create_index(
        "ix_product_image_gen_tasks_anonymous_user_id",
        "product_image_gen_tasks",
        ["anonymous_user_id"],
    )
    op.create_index("ix_product_image_gen_tasks_job_id", "product_image_gen_tasks", ["job_id"])
    op.create_index("ix_product_image_gen_tasks_status", "product_image_gen_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("product_image_gen_tasks")
    op.drop_table("product_info_prompt_templates")
    op.drop_table("product_info_job_steps")
    op.drop_table("product_info_jobs")
