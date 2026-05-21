"""告警规则读模型（管理面 DTO，不含 ORM）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid


@dataclass(frozen=True, slots=True)
class AlertRuleSummary:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    metric: str
    threshold: Decimal
    window_minutes: int
    channels: dict[str, Any]
    enabled: bool
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


def alert_rule_from_orm(row: object) -> AlertRuleSummary:
    """从 ``GatewayAlertRule`` ORM 行构建摘要。"""
    return AlertRuleSummary(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description,
        metric=row.metric,
        threshold=row.threshold,
        window_minutes=row.window_minutes,
        channels=dict(row.channels or {}),
        enabled=row.enabled,
        last_triggered_at=row.last_triggered_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = ["AlertRuleSummary", "alert_rule_from_orm"]
