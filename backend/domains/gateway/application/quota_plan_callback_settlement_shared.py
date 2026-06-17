"""Provider / Entitlement callback 配额结算共享解析与 Redis 幂等辅助。"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from decimal import Decimal
from typing import Protocol
import uuid

from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_plan_quota
from domains.gateway.domain.quota_plan import (
    PlanQuotaSpec,
    QuotaPlanReservation,
    normalize_reset_strategy,
)
from libs.db.redis import get_redis_client

SETTLEMENT_ONCE_TTL_SECONDS = 86400


class _PlanQuotaRow(Protocol):
    id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    reset_strategy: str
    reset_timezone: str
    reset_time_minutes: int
    reset_day_of_month: int


def to_plan_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(value))
    return None


def parse_plan_reservations(
    raw: object,
    *,
    plan_id: uuid.UUID,
    specs_by_quota_id: dict[uuid.UUID, PlanQuotaSpec],
) -> list[QuotaPlanReservation]:
    if not isinstance(raw, list):
        return []
    reservations: list[QuotaPlanReservation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        quota_id = to_plan_uuid(item.get("quota_id"))
        if quota_id is None:
            continue
        spec = specs_by_quota_id.get(quota_id)
        if spec is None:
            continue
        minute_raw = item.get("minute_unix")
        reserved_raw = item.get("reserved_requests", 1)
        try:
            minute_unix = int(minute_raw)
            reserved_requests = int(reserved_raw)
        except (TypeError, ValueError):
            continue
        reservations.append(
            QuotaPlanReservation(
                plan_id=plan_id,
                spec=spec,
                minute_unix=minute_unix,
                reserved_requests=reserved_requests,
            )
        )
    return reservations


def build_specs_by_quota_id(
    *,
    plan_valid_from: datetime | None,
    quotas: list[_PlanQuotaRow],
) -> dict[uuid.UUID, PlanQuotaSpec]:
    return {
        row.id: PlanQuotaSpec(
            quota_id=row.id,
            label=row.label,
            window_seconds=row.window_seconds,
            limit_usd=row.limit_usd,
            limit_tokens=row.limit_tokens,
            limit_requests=row.limit_requests,
            reset_strategy=normalize_reset_strategy(row.reset_strategy),
            plan_valid_from=plan_valid_from,
            period_reset_anchor=period_reset_anchor_from_plan_quota(
                reset_timezone=row.reset_timezone,
                reset_time_minutes=row.reset_time_minutes,
                reset_day_of_month=row.reset_day_of_month,
            ),
        )
        for row in quotas
    }


async def acquire_settlement_once(key: str) -> bool:
    client = await get_redis_client()
    acquired = await client.set(key, "1", nx=True, ex=SETTLEMENT_ONCE_TTL_SECONDS)
    return bool(acquired)


__all__ = [
    "SETTLEMENT_ONCE_TTL_SECONDS",
    "acquire_settlement_once",
    "build_specs_by_quota_id",
    "parse_plan_reservations",
    "to_plan_uuid",
]
