"""
GatewayVirtualKey Model - 网关虚拟 Key

外部客户端通过 Bearer ``sk-gw-...`` 或 ``x-api-key`` 调用 /v1/* 时使用的 Key。
复用 [`api_key.py`](backend/domains/identity/infrastructure/models/api_key.py) 的 hash/掩码模式。
"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayVirtualKey(BaseModel):
    """虚拟 Key

    业务规则：
    - 前缀固定 `sk-gw-`
    - key_hash 唯一索引
    - allowed_models 为空表示允许所有
    - is_system=True 的 key 由内部桥接层使用，UI 不展示
    """

    __tablename__ = "gateway_virtual_keys"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Key 信息
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, server_default="sk-gw-")
    key_id: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="随机标识符（16 字符），用于日志识别",
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    encrypted_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Fernet 加密后的完整 Key（用户首次创建后查看）",
    )

    # 权限白名单
    allowed_models: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)),
        nullable=False,
        server_default="{}",
    )
    allowed_capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)),
        nullable=False,
        server_default="{}",
    )

    # 限流（vkey 维度，None 表示不限）
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 行为开关
    store_full_messages: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="是否在日志中保存完整 prompt/response（否则仅 hash）",
    )
    guardrail_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="是否启用 PII Guardrail",
    )

    # 系统 Key 标识（用于内部桥接，UI 不展示）
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        index=True,
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    @property
    def masked_key_display(self) -> str:
        return f"{self.key_prefix}{self.key_id[:4]}...***"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def __repr__(self) -> str:
        return f"<GatewayVirtualKey {self.masked_key_display} team={self.team_id}>"


__all__ = ["GatewayVirtualKey"]
