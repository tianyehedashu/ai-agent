"""Callback 侧上游 ProviderPlan 配额结算（pre_call reserve → success commit / failure release）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.provider_plan_guard import get_provider_plan_guard
from domains.gateway.application.quota_plan_callback_settlement_shared import (
    acquire_settlement_once,
    build_specs_by_quota_id,
    parse_plan_reservations,
    to_plan_uuid,
)
from domains.gateway.application.quota_plan_usage_persist import schedule_quota_plan_usage_upsert
from domains.gateway.domain.quota_plan import PROVIDER_NS, PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.infrastructure.repositories.provider_plan_repository import (
    ProviderPlanRepository,
)
from libs.db.database import get_session_context

_PLAN_ID_KEY = "gateway_provider_plan_id"
_RESERVATIONS_KEY = "gateway_provider_plan_reservations"
_SETTLED_PREFIX = "gateway:quota:provider_settled:"
_RELEASED_PREFIX = "gateway:quota:provider_released:"

_acquire_once = acquire_settlement_once


async def _load_plan_specs(plan_id: uuid.UUID) -> dict[uuid.UUID, PlanQuotaSpec]:
    async with get_session_context() as session:
        repo = ProviderPlanRepository(session)
        plan = await repo.get(plan_id)
        if plan is None:
            return {}
        quotas = await repo.list_quotas(plan_id)
    return build_specs_by_quota_id(plan_valid_from=plan.valid_from, quotas=quotas)


def _parse_reservations(
    raw: object,
    *,
    plan_id: uuid.UUID,
    specs_by_quota_id: dict[uuid.UUID, PlanQuotaSpec],
) -> list[QuotaPlanReservation]:
    return parse_plan_reservations(
        raw,
        plan_id=plan_id,
        specs_by_quota_id=specs_by_quota_id,
    )


async def settle_provider_plan_from_callback(
    *,
    metadata: dict[str, Any],
    status: str,
    cost_usd: Decimal,
    total_tokens: int,
    request_id: str | None,
) -> None:
    """成功：累加真实 token/cost；失败：释放 pre_call 预扣的 requests。"""
    plan_id = to_plan_uuid(metadata.get(_PLAN_ID_KEY))
    if plan_id is None:
        return

    specs_by_quota_id = await _load_plan_specs(plan_id)
    if not specs_by_quota_id:
        return

    reservations = _parse_reservations(
        metadata.get(_RESERVATIONS_KEY),
        plan_id=plan_id,
        specs_by_quota_id=specs_by_quota_id,
    )
    guard = get_provider_plan_guard()

    if status == "success":
        if total_tokens <= 0 and cost_usd <= 0:
            return
        if request_id and not await _acquire_once(f"{_SETTLED_PREFIX}{request_id}"):
            return
        specs = (
            [r.spec for r in reservations]
            if reservations
            else list(specs_by_quota_id.values())
        )
        settled_at = datetime.now(UTC)
        await guard.commit(
            plan_id,
            specs,
            delta_tokens=total_tokens,
            delta_usd=cost_usd,
        )
        if request_id:
            schedule_quota_plan_usage_upsert(
                ns=PROVIDER_NS,
                plan_id=plan_id,
                specs=specs,
                delta_tokens=total_tokens,
                delta_cost_usd=cost_usd,
                request_id=request_id,
                settled_at=settled_at,
            )
        return

    if not reservations:
        return
    if request_id and not await _acquire_once(f"{_RELEASED_PREFIX}{request_id}"):
        return
    await guard.release(plan_id, reservations)


__all__ = ["settle_provider_plan_from_callback"]
