"""add_api_keys

Revision ID: c1d2e3f4g5h6
Revises: b9c4d5e6f8g9
Create Date: 2026-01-27 18:00:00.000000

添加 API Key 管理功能
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4g5h6"
down_revision: str | None = "b9c4d5e6f8g9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 API Key 相关表"""

    # 检查表是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "api_keys" not in tables:
        # 创建 api_keys 表
        op.create_table(
            "api_keys",
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
                comment="所属用户 ID",
            ),
            sa.Column(
                "key_hash",
                sa.String(255),
                nullable=False,
                unique=True,
                comment="bcrypt 哈希后的 API Key",
            ),
            sa.Column(
                "key_prefix",
                sa.String(10),
                nullable=False,
                default="sk_",
                comment="Key 前缀，如 'sk_'",
            ),
            sa.Column(
                "key_id",
                sa.String(16),
                nullable=False,
                comment="随机标识符（16字符），用于日志识别",
            ),
            sa.Column(
                "name",
                sa.String(100),
                nullable=False,
                comment="用户自定义名称",
            ),
            sa.Column(
                "description",
                sa.Text(),
                nullable=True,
                comment="描述",
            ),
            sa.Column(
                "scopes",
                ARRAY(sa.String),
                nullable=False,
                default=list,
                comment="权限范围数组",
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="过期时间（必填）",
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                default=True,
                comment="是否激活",
            ),
            sa.Column(
                "last_used_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最后使用时间",
            ),
            sa.Column(
                "usage_count",
                sa.Integer(),
                nullable=False,
                default=0,
                comment="使用次数",
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

        # 创建索引
        op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
        op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
        op.create_index("ix_api_keys_key_id", "api_keys", ["key_id"])
        op.create_index("ix_api_keys_expires_at", "api_keys", ["expires_at"])
        op.create_index("ix_api_keys_is_active", "api_keys", ["is_active"])

    if "api_key_usage_logs" not in tables:
        # 创建 api_key_usage_logs 表
        op.create_table(
            "api_key_usage_logs",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "api_key_id",
                UUID(as_uuid=True),
                nullable=False,
                comment="关联的 API Key ID",
            ),
            sa.Column(
                "endpoint",
                sa.String(255),
                nullable=False,
                comment="请求端点",
            ),
            sa.Column(
                "method",
                sa.String(10),
                nullable=False,
                comment="HTTP 方法",
            ),
            sa.Column(
                "ip_address",
                sa.String(45),
                nullable=True,
                comment="客户端 IP",
            ),
            sa.Column(
                "user_agent",
                sa.Text(),
                nullable=True,
                comment="User-Agent",
            ),
            sa.Column(
                "status_code",
                sa.Integer(),
                nullable=False,
                comment="HTTP 状态码",
            ),
            sa.Column(
                "response_time_ms",
                sa.Integer(),
                nullable=True,
                comment="响应时间（毫秒）",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

        # 创建索引
        op.create_index("ix_api_key_usage_logs_api_key_id", "api_key_usage_logs", ["api_key_id"])
        op.create_index("ix_api_key_usage_logs_created_at", "api_key_usage_logs", ["created_at"])


def downgrade() -> None:
    """删除 API Key 相关表"""
    op.drop_table("api_key_usage_logs")
    op.drop_table("api_keys")
