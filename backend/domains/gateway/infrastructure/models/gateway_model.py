"""
GatewayModel - 模型注册表

把"虚拟模型名"映射到"真实模型 + provider + 凭据"。
"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayModel(BaseModel):
    """模型注册表

    业务规则：
    - 同一 team 下 name 唯一
    - team_id NULL 表示系统级模型（所有团队都可用）
    - capability 决定该模型能被哪些 endpoint 调用（chat/embedding/...）
    """

    __tablename__ = "gateway_models"

    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="虚拟模型别名（客户端使用）",
    )
    capability: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="chat / embedding / image / audio_transcription / audio_speech / rerank",
    )
    real_model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="真实模型标识，如 deepseek/deepseek-chat、gpt-4o 等",
    )
    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_credentials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
        JSONB, nullable=True, comment="扩展标签：cost_per_token、context_window、prompt_cache 等"
    )

    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_gateway_models_team_name"),
        Index("ix_gateway_models_lookup", "team_id", "capability", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<GatewayModel {self.name} -> {self.provider}/{self.real_model}>"


__all__ = ["GatewayModel"]
