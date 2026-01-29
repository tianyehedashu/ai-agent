"""add_llm_key_quota_tables

Revision ID: g5h6i7j8k9l0
Revises: f4g5h6i7j8k9
Create Date: 2026-01-28 10:00:00.000000

添加用户 LLM Key 与配额相关表：
- user_provider_configs: 用户提供商配置
- user_quotas: 用户配额
- quota_usage_logs: 配额用量日志
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g5h6i7j8k9l0"
down_revision: str | None = "f4g5h6i7j8k9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 user_provider_configs、user_quotas、quota_usage_logs 表"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "user_provider_configs" not in tables:
        op.create_table(
            "user_provider_configs",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                nullable=False,
                index=True,
                comment="所属用户 ID",
            ),
            sa.Column(
                "provider",
                sa.String(50),
                nullable=False,
                index=True,
                comment="提供商标识: openai, anthropic, dashscope, zhipuai, deepseek, volcengine",
            ),
            sa.Column(
                "api_key",
                sa.Text(),
                nullable=False,
                comment="加密存储的 API Key",
            ),
            sa.Column(
                "api_base",
                sa.String(255),
                nullable=True,
                comment="自定义 API Base URL（可选）",
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
                index=True,
                comment="是否启用",
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
            sa.UniqueConstraint("user_id", "provider", name="uq_user_provider_config"),
        )

    if "user_quotas" not in tables:
        op.create_table(
            "user_quotas",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                nullable=False,
                unique=True,
                index=True,
                comment="所属用户 ID（一对一）",
            ),
            sa.Column(
                "daily_text_requests",
                sa.Integer(),
                nullable=True,
                comment="每日文本请求数上限（None 表示无限制）",
            ),
            sa.Column(
                "daily_image_requests",
                sa.Integer(),
                nullable=True,
                comment="每日图像生成数上限",
            ),
            sa.Column(
                "daily_embedding_requests",
                sa.Integer(),
                nullable=True,
                comment="每日 Embedding 请求数上限",
            ),
            sa.Column(
                "monthly_token_limit",
                sa.Integer(),
                nullable=True,
                comment="每月 Token 上限",
            ),
            sa.Column(
                "current_daily_text",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="当前每日文本请求已用量",
            ),
            sa.Column(
                "current_daily_image",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="当前每日图像生成已用量",
            ),
            sa.Column(
                "current_daily_embedding",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="当前每日 Embedding 已用量",
            ),
            sa.Column(
                "current_monthly_tokens",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="当前每月 Token 已用量",
            ),
            sa.Column(
                "daily_reset_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="每日配额下次重置时间",
            ),
            sa.Column(
                "monthly_reset_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="每月配额下次重置时间",
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

    if "quota_usage_logs" not in tables:
        op.create_table(
            "quota_usage_logs",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                nullable=False,
                index=True,
                comment="用户 ID",
            ),
            sa.Column(
                "capability",
                sa.String(20),
                nullable=False,
                index=True,
                comment="能力类型: text, image, embedding",
            ),
            sa.Column(
                "provider",
                sa.String(50),
                nullable=False,
                index=True,
                comment="提供商: openai, anthropic, dashscope, etc.",
            ),
            sa.Column(
                "model",
                sa.String(100),
                nullable=True,
                comment="模型名称",
            ),
            sa.Column(
                "key_source",
                sa.String(10),
                nullable=False,
                index=True,
                comment="Key 来源: user 或 system",
            ),
            sa.Column(
                "input_tokens",
                sa.Integer(),
                nullable=True,
                comment="输入 Token 数",
            ),
            sa.Column(
                "output_tokens",
                sa.Integer(),
                nullable=True,
                comment="输出 Token 数",
            ),
            sa.Column(
                "image_count",
                sa.Integer(),
                nullable=True,
                comment="生成图像数",
            ),
            sa.Column(
                "cost_estimate",
                sa.Numeric(10, 4),
                nullable=True,
                comment="估算费用（美元）",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
                comment="创建时间",
            ),
        )


def downgrade() -> None:
    """删除 user_provider_configs、user_quotas、quota_usage_logs 表"""
    op.drop_table("quota_usage_logs", if_exists=True)
    op.drop_table("user_quotas", if_exists=True)
    op.drop_table("user_provider_configs", if_exists=True)
