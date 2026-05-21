"""
GatewayModel - 模型注册表

把"虚拟模型名"映射到"真实模型 + provider + 凭据"。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class GatewayModel(BaseModel, TenantScopedMixin):
    """模型注册表（仅租户行；系统级见 ``system_gateway_models``）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "gateway_models"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="虚拟模型别名（客户端使用）",
    )
    capability: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment=(
            "主调用面: chat / embedding / image / video_generation / moderation / "
            "audio_transcription / audio_speech / rerank（与 OpenAI 兼容路由入口对齐）"
        ),
    )
    real_model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="真实模型标识，如 deepseek/deepseek-chat、gpt-4o 等",
    )
    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs provider_credentials.id (no DB FK)",
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    weight: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
        comment="加权路由权重",
    )
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    tags: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "扩展标签：cost_per_token、context_window、prompt_cache；"
            "视频目录：supports_video_gen、video_vendor_model_id（或 giikin_video_model）、"
            "video_durations（整数秒列表）"
        ),
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_gateway_models_tenant_name"),
        Index("ix_gateway_models_lookup", "tenant_id", "capability", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<GatewayModel {self.name} -> {self.provider}/{self.real_model}>"


__all__ = ["GatewayModel"]
