"""
UserProviderConfig Model - 用户 LLM 提供商配置模型

存储用户自己配置的大模型提供商 API Key。
用户配置了 Key 后，使用自己的 Key 调用不受配额限制。
"""

import uuid

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TimestampMixin


class UserProviderConfig(BaseModel, TimestampMixin):
    """用户 LLM 提供商配置

    存储用户自己的大模型提供商 API Key 配置。
    支持的提供商: openai, anthropic, dashscope, zhipuai, deepseek, volcengine

    设计决策：
    - api_key 字段存储加密后的密钥（加解密在 Service 层处理）
    - 同一用户同一提供商只能有一条配置（唯一约束）
    - is_active 用于软禁用，不删除历史配置
    """

    __tablename__ = "user_provider_configs"

    # 用户关联
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属用户 ID",
    )

    # 提供商信息
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="提供商标识: openai, anthropic, dashscope, zhipuai, deepseek, volcengine",
    )

    # API 配置
    api_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="加密存储的 API Key",
    )
    api_base: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="自定义 API Base URL（可选）",
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        index=True,
        comment="是否启用",
    )

    # 唯一约束：同一用户同一提供商只能有一条配置
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_config"),)

    def __repr__(self) -> str:
        return f"<UserProviderConfig user={self.user_id} provider={self.provider}>"
