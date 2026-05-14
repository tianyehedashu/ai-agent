"""
GatewayMetricsHourly - 小时级聚合表

由 rollup job 从 GatewayRequestLog 增量聚合，仪表盘读它而非扫全表。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayMetricsHourly(BaseModel):
    """小时级聚合"""

    __tablename__ = "gateway_metrics_hourly"

    bucket_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="小时桶起始时刻（UTC）",
    )

    # 维度
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    vkey_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    real_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    capability: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # 指标
    requests: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 6), nullable=False, server_default="0", default=Decimal("0")
    )
    total_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="累计 latency_ms，用于计算平均",
    )
    p95_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cache_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "bucket_at",
            "team_id",
            "user_id",
            "vkey_id",
            "credential_id",
            "provider",
            "real_model",
            "capability",
            name="uq_gateway_metrics_hourly_dim",
        ),
        Index("ix_gateway_metrics_hourly_team_bucket", "team_id", "bucket_at"),
    )

    def __repr__(self) -> str:
        return f"<GatewayMetricsHourly {self.bucket_at} team={self.team_id} req={self.requests}>"


__all__ = ["GatewayMetricsHourly"]
