"""
ProviderCredential Model - 统一 LLM 提供商凭据模型

替代原有的 UserProviderConfig 与 UserModel.api_key_encrypted，
为 system / team / user 三级作用域提供统一的凭据池。

GatewayModel.credential_id 引用此表，使路由配置不需要内嵌 api_key。
"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class ProviderCredential(BaseModel):
    """LLM 提供商凭据

    作用域：
    - system：全局共享凭据，仅平台 admin 管理（scope_id 为 NULL）
    - team：团队凭据，团队成员共享（scope_id = team_id）
    - user：用户私有凭据，由 Settings 页面管理（scope_id = user_id）

    业务规则：
    - 同 scope + scope_id + provider + name 唯一
    - api_key_encrypted 使用 libs.crypto Fernet 加密
    """

    __tablename__ = "provider_credentials"

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="作用域: system / team / user",
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="作用域内对应实体 ID（system 为 NULL）",
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="提供商: openai / anthropic / dashscope / zhipuai / deepseek / volcengine / custom",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="凭据展示名（同 scope 下 provider+name 唯一）",
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="加密存储的 API Key（Fernet）",
    )
    api_base: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="自定义 API Base URL",
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="扩展字段：endpoint_id / region / org / project_id 等",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # 来源标识：用于灰度迁移历史数据
    legacy_user_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="迁移自 user_provider_configs 的源记录 ID",
    )
    legacy_user_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="迁移自 user_models 的源记录 ID",
    )

    __table_args__ = (
        UniqueConstraint(
            "scope", "scope_id", "provider", "name", name="uq_provider_credentials_scope_name"
        ),
        Index("ix_provider_credentials_scope_lookup", "scope", "scope_id", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderCredential {self.scope}:{self.scope_id} "
            f"{self.provider}:{self.name}>"
        )


__all__ = ["ProviderCredential"]
