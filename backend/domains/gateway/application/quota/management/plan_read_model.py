"""Gateway 套餐只读模型（application 层，供 presentation 映射，禁止 ORM 泄漏）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PlanQuotaReadModel:
    id: UUID
    label: str
    window_seconds: int
    reset_strategy: str
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    unit_price_usd_per_token: Decimal | None = None
    unit_price_usd_per_request: Decimal | None = None
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    limit_images: int | None = None


@dataclass(frozen=True)
class ProviderQuotaReadModel:
    """上游扁平配额规则：一行 = 一条规则。"""

    id: UUID
    credential_id: UUID
    real_model: str | None
    label: str
    window_seconds: int
    reset_strategy: str
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    limit_images: int | None = None


@dataclass(frozen=True)
class EntitlementPlanReadModel:
    id: UUID
    scope: str
    scope_id: UUID
    label: str
    valid_from: datetime
    included_models: tuple[str, ...]
    included_capabilities: tuple[str, ...]
    notes: str | None
    extra: dict[str, Any] | None
    quotas: tuple[PlanQuotaReadModel, ...]


__all__ = [
    "EntitlementPlanReadModel",
    "PlanQuotaReadModel",
    "ProviderQuotaReadModel",
]
