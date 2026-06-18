"""Callback 侧上游扁平 ProviderQuota 配额结算。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.provider_quota_config_cache import (
    ProviderQuotaConfigRow,
    quota_row_to_spec,
)
from domains.gateway.application.provider_quota_guard import (
    ProviderQuotaReservation,
    get_provider_quota_guard,
)
from domains.gateway.application.quota_plan_callback_settlement_shared import (
    acquire_settlement_once,
    parse_flat_quota_reservations,
    to_plan_uuid,
)
from domains.gateway.application.quota_plan_usage_persist import schedule_quota_plan_usage_upsert
from domains.gateway.domain.quota_plan import PROVIDER_NS, PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.infrastructure.repositories.provider_quota_repository import (
    ProviderQuotaRepository,
)
from libs.db.database import get_session_context

_RESERVATIONS_KEY = "gateway_provider_quota_reservations"
_SETTLED_PREFIX = "gateway:quota:provider_settled:"
_RELEASED_PREFIX = "gateway:quota:provider_released:"


async def _load_rule_specs(rule_ids: list[uuid.UUID]) -> dict[uuid.UUID, PlanQuotaSpec]:
    """单 session 批量加载规则 spec，消除按 rule_id 逐个开 session 的开销。"""
    if not rule_ids:
        return {}
    async with get_session_context() as session:
        repo = ProviderQuotaRepository(session)
        rows = await repo.get_many(rule_ids)
    return {
        rid: quota_row_to_spec(
            ProviderQuotaConfigRow(
                rule_id=row.id,
                label=row.label,
                window_seconds=row.window_seconds,
                reset_strategy=row.reset_strategy,
                reset_timezone=row.reset_timezone,
                reset_time_minutes=row.reset_time_minutes,
                reset_day_of_month=row.reset_day_of_month,
                limit_usd=row.limit_usd,
                limit_tokens=row.limit_tokens,
                limit_requests=row.limit_requests,
                enabled=row.enabled,
                valid_from=row.valid_from,
                valid_until=row.valid_until,
            )
        )
        for rid, row in rows.items()
    }


def _reservations_raw(metadata: dict[str, Any]) -> object | None:
    raw = metadata.get(_RESERVATIONS_KEY)
    return raw if raw else None


def _rule_ids_from_raw(raw: object, metadata: dict[str, Any]) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                rid = to_plan_uuid(item.get("rule_id")) or to_plan_uuid(item.get("quota_id"))
                if rid is not None and rid not in ids:
                    ids.append(rid)
    if not ids:
        primary = to_plan_uuid(metadata.get("gateway_provider_plan_id"))
        if primary is not None:
            ids.append(primary)
    return ids


async def settle_provider_quota_from_callback(
    *,
    metadata: dict[str, Any],
    status: str,
    cost_usd: Decimal,
    total_tokens: int,
    request_id: str | None,
) -> None:
    raw = _reservations_raw(metadata)
    rule_ids = _rule_ids_from_raw(raw, metadata) if raw is not None else []
    if not rule_ids:
        primary = to_plan_uuid(metadata.get("gateway_provider_plan_id"))
        if primary is not None:
            rule_ids = [primary]
    if not rule_ids:
        return

    specs_by_rule = await _load_rule_specs(rule_ids)
    if not specs_by_rule:
        return

    reservations = (
        parse_flat_quota_reservations(raw, specs_by_rule_id=specs_by_rule)
        if raw is not None
        else []
    )
    guard = get_provider_quota_guard()

    if status == "success":
        if total_tokens <= 0 and cost_usd <= 0:
            return
        if request_id and not await acquire_settlement_once(f"{_SETTLED_PREFIX}{request_id}"):
            return
        settled_at = datetime.now(UTC)
        commit_targets = reservations or [
            QuotaPlanReservation(
                plan_id=rid,
                spec=spec,
                minute_unix=0,
                reserved_requests=0,
            )
            for rid, spec in specs_by_rule.items()
        ]
        for res in commit_targets:
            await guard.commit_rule(
                res.plan_id,
                res.spec,
                delta_tokens=total_tokens,
                delta_usd=cost_usd,
            )
            if request_id:
                schedule_quota_plan_usage_upsert(
                    ns=PROVIDER_NS,
                    plan_id=res.plan_id,
                    specs=[res.spec],
                    delta_tokens=total_tokens,
                    delta_cost_usd=cost_usd,
                    request_id=request_id,
                    settled_at=settled_at,
                )
        return

    if not reservations:
        return
    if request_id and not await acquire_settlement_once(f"{_RELEASED_PREFIX}{request_id}"):
        return
    for res in reservations:
        await guard.release_rule(
            ProviderQuotaReservation(rule_id=res.plan_id, spec=res.spec, reservation=res)
        )


__all__ = ["settle_provider_quota_from_callback"]
