"""
GatewayRequestLog - 调用日志（按月分区）

每次 LiteLLM 调用可写一条（成功请求受 ``gateway_request_log_success_sample_rate`` 等配置约束）。
冗余存储 user/team/vkey/route 快照，避免删除/改名后失真。

注意：
- 主表 `gateway_request_logs` 由 alembic 创建为按 created_at 月分区的 PARTITION BY RANGE 表
- 子分区表由 `gateway_partition_job` 后台任务每月维护
- 早于 ``gateway_request_log_retention_days`` 的整月分区由 `gateway_request_log_retention_loop` 删除（若配置）
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.database import Base


class GatewayRequestLog(Base):
    """调用日志

    使用 Base 而非 BaseModel：因为这是分区表，主键是 (id, created_at)。
    """

    __tablename__ = "gateway_request_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # 归属（删除原实体时置 NULL，保留快照）
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    vkey_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # 快照（防止级联删除/改名导致历史失真）
    team_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    user_email_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vkey_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 调用信息
    capability: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    route_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    real_model: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # 状态
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="success / failed / rate_limited / budget_exceeded / guardrail_blocked",
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Token & Cost
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    cached_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default="0", default=Decimal("0")
    )

    # 性能
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    ttfb_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 缓存与回退
    cache_hit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    fallback_chain: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )

    # 请求/响应（脱敏后）
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metadata_extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_gateway_request_logs_team_time", "team_id", "created_at"),
        Index("ix_gateway_request_logs_user_time", "user_id", "created_at"),
        Index("ix_gateway_request_logs_vkey_time", "vkey_id", "created_at"),
        Index("ix_gateway_request_logs_status_time", "status", "created_at"),
        # 分区配置（在 alembic 中显式声明 PARTITION BY RANGE (created_at)）
        {"postgresql_partition_by": "RANGE (created_at)"},
    )


__all__ = ["GatewayRequestLog"]
