"""
Alert Models - 告警规则与事件
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayAlertRule(BaseModel):
    """告警规则"""

    __tablename__ = "gateway_alert_rules"

    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="error_rate / budget_usage / latency_p95 / request_rate",
    )
    threshold: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5", default=5
    )
    channels: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="通知渠道配置：{webhook: url, email: [...], inapp: true}",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_gateway_alert_rules_lookup", "team_id", "enabled"),)

    def __repr__(self) -> str:
        return f"<GatewayAlertRule {self.name} {self.metric}>"


class GatewayAlertEvent(BaseModel):
    """告警事件（命中规则后落库）"""

    __tablename__ = "gateway_alert_events"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    metric_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    threshold: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="warning"
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    acknowledged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    def __repr__(self) -> str:
        return f"<GatewayAlertEvent rule={self.rule_id} value={self.metric_value}>"


__all__ = ["GatewayAlertEvent", "GatewayAlertRule"]
