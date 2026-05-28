"""系统级 Gateway 配置表（无 tenant_id，与多租户业务表分离）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class SystemProviderCredential(BaseModel):
    """平台级 Provider 凭据（与 ``provider_credentials`` 租户/BYOK 行分离）。"""

    __tablename__ = "system_provider_credentials"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_base: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="OpenAI-compat API Base URL（legacy 镜像）",
    )
    api_bases: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="各协议 endpoint 覆盖：openai_compat / anthropic_native",
    )
    profile_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="上游方案 ID；NULL 表示 provider.default",
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="public", server_default="public", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("provider", "name", name="uq_system_provider_credentials_provider_name"),
    )


class SystemGatewayModel(BaseModel):
    __tablename__ = "system_gateway_models"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    real_model: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs system_provider_credentials.id (no DB FK)",
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="inherit", server_default="inherit", nullable=False
    )
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    upstream_call_shape: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="出站 LiteLLM 调用形：openai_compat / anthropic_native",
    )
    last_test_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("name", name="uq_system_gateway_models_name"),
        Index("ix_system_gateway_models_lookup", "capability", "enabled"),
    )


class SystemGatewayRoute(BaseModel):
    __tablename__ = "system_gateway_routes"

    virtual_model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    primary_models: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_general: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_content_policy: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_context_window: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    strategy: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="simple-shuffle"
    )
    retry_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("virtual_model", name="uq_system_gateway_routes_virtual_model"),
    )


class SystemGatewayAlertRule(BaseModel):
    __tablename__ = "system_gateway_alert_rules"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5", default=5
    )
    channels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_system_gateway_alert_rules_enabled",
            "name",
            postgresql_where=text("enabled IS TRUE"),
        ),
    )


class SystemGatewayGrant(BaseModel):
    """系统级凭据/模型对 team 或 user 的可见性白名单（仅 restricted 时生效）。"""

    __tablename__ = "system_gateway_grants"

    subject_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "subject_kind",
            "subject_id",
            "target_kind",
            "target_id",
            name="uq_system_gateway_grants_subject_target",
        ),
        Index("ix_system_gateway_grants_subject", "subject_kind", "subject_id"),
        Index("ix_system_gateway_grants_target", "target_kind", "target_id"),
    )


__all__ = [
    "SystemGatewayAlertRule",
    "SystemGatewayGrant",
    "SystemGatewayModel",
    "SystemGatewayRoute",
    "SystemProviderCredential",
]
