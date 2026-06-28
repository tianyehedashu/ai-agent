"""告警规则快照（租户 + 系统级统一，供 job / 仓储使用）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid


@dataclass(frozen=True, slots=True)
class AlertRuleSnapshot:
    rule_id: uuid.UUID
    tenant_id: uuid.UUID | None
    is_system: bool
    name: str
    metric: str
    threshold: Decimal
    window_minutes: int
    channels: dict[str, Any]
    last_triggered_at: datetime | None


__all__ = ["AlertRuleSnapshot"]
