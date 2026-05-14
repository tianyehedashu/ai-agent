"""
User Model - 用户自定义模型配置

用户可配置自带 API Key 的 LLM 模型，其他用户不可见。
模型类型：text（文本）、image（图片）、video（视频），支持多选。
"""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, OwnedMixin


class UserModel(BaseModel, OwnedMixin):
    """用户自定义模型"""

    __tablename__ = "user_models"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    anonymous_user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="显示名称",
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="提供商: openai/deepseek/dashscope/anthropic/zhipuai/volcengine/custom",
    )
    model_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="模型标识, 如 gpt-4o, deepseek-chat",
    )
    api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="加密存储的 API Key (Fernet)",
    )
    api_base: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="自定义 API 端点",
    )
    model_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)),
        nullable=False,
        comment="模型类型: text, image, video",
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="扩展配置 {context_window, supports_vision, supports_tools, max_tokens, ...}",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用",
    )
    last_test_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="上次连通性测试结果: success / failed / NULL=未测过",
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次连通性测试时间",
    )
    last_test_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="上次连通性测试说明（失败原因等）；成功时为 NULL",
    )

    def __repr__(self) -> str:
        return f"<UserModel {self.id} {self.display_name} ({self.provider}/{self.model_id})>"
