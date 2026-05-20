"""
ProviderCredential Model - 统一 LLM 提供商凭据模型

为 system / team / user 三级作用域提供统一的凭据池。

GatewayModel.credential_id 引用此表，使路由配置不需要内嵌 api_key。
"""

from __future__ import annotations

from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class ProviderCredential(BaseModel):
    """LLM 提供商凭据

    作用域：
    - 租户凭据：``tenant_id`` 非空（团队/workspace）；系统级见 ``system_provider_credentials``（禁止再写 ``scope=system``）
    - 用户 BYOK：``scope='user'`` + ``scope_id=user_id``；``tenant_id`` 与 ``scope`` 互斥
    - 用户 BYOK：``scope='user'`` + ``scope_id=user_id``（``tenant_id`` 为空）

    业务规则：
    - 租户行：``tenant_id + provider + name`` 唯一；用户行：``scope + scope_id + provider + name`` 唯一
    - api_key_encrypted 使用 libs.crypto Fernet 加密
    """

    __tablename__ = "provider_credentials"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="租户（团队）凭据归属；与 scope=user 互斥",
    )
    scope: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="仅 user BYOK 时为 'user'",
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="BYOK 用户 ID（scope=user）",
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

    __table_args__ = (
        Index(
            "uq_provider_credentials_tenant_provider_name",
            "tenant_id",
            "provider",
            "name",
            unique=True,
            postgresql_where=sa.text("tenant_id IS NOT NULL"),
        ),
        Index(
            "uq_provider_credentials_user_scope_name",
            "scope",
            "scope_id",
            "provider",
            "name",
            unique=True,
            postgresql_where=sa.text("scope = 'user'"),
        ),
        Index("ix_provider_credentials_scope_lookup", "scope", "scope_id", "provider"),
    )

    def __repr__(self) -> str:
        if self.tenant_id is not None:
            return f"<ProviderCredential tenant:{self.tenant_id} {self.provider}:{self.name}>"
        return f"<ProviderCredential {self.scope}:{self.scope_id} {self.provider}:{self.name}>"


__all__ = ["ProviderCredential"]
