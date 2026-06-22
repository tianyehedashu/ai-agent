"""Callback 侧下游 EntitlementPlan 配额结算（与 ProviderPlan 对称）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.quota_plan_callback_settlement_shared import (
    SETTLEMENT_ONCE_TTL_SECONDS,
    acquire_settlement_once,
    build_specs_by_quota_id,
    parse_plan_reservations,
    to_plan_uuid,
)
from domains.gateway.application.quota_plan_service import get_quota_plan_service
from domains.gateway.application.quota_plan_usage_persist import schedule_quota_plan_usage_upsert
from domains.gateway.domain.quota_plan import (
    ENTITLEMENT_NS,
    PlanQuotaSpec,
    QuotaPlanReservation,
)
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from libs.db.database import get_session_context
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)

_RESERVATIONS_META_KEY = "gateway_entitlement_plan_reservations"
_LEGACY_RESERVATIONS_META_KEY = "_gateway_entitlement_plan_reservations"
_SETTLED_PREFIX = "gateway:quota:entitlement_settled:"
_RELEASED_PREFIX = "gateway:quota:entitlement_released:"
_PROXY_SETTLED_PREFIX = "gateway:quota:entitlement_proxy_settled:"

_acquire_once = acquire_settlement_once


async def _load_plan_specs(plan_id: uuid.UUID) -> dict[uuid.UUID, PlanQuotaSpec]:
    async with get_session_context() as session:
        repo = EntitlementPlanRepository(session)
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


async def record_proxy_entitlement_commit(request_id: str) -> None:
    """proxy ``settle_usage`` 已 commit 下游套餐时标记，callback 不再重复累加。"""
    if not request_id:
        return
    client = await get_redis_client()
    await client.set(
        f"{_PROXY_SETTLED_PREFIX}{request_id}",
        "1",
        ex=SETTLEMENT_ONCE_TTL_SECONDS,
    )


async def record_proxy_entitlement_released(request_id: str) -> None:
    """proxy 失败路径已 release 预扣时标记。"""
    if not request_id:
        return
    client = await get_redis_client()
    await client.set(f"{_RELEASED_PREFIX}{request_id}", "1", ex=SETTLEMENT_ONCE_TTL_SECONDS)


async def settle_entitlement_plan_from_callback(
    *,
    metadata: dict[str, Any],
    status: str,
    cost_usd: Decimal,
    total_tokens: int,
    request_id: str | None,
    kwargs: dict[str, Any] | None = None,
) -> None:
    _ = kwargs
    plan_id = to_plan_uuid(metadata.get("gateway_entitlement_plan_id"))
    if plan_id is None:
        return

    specs_by_quota_id = await _load_plan_specs(plan_id)
    if not specs_by_quota_id:
        return

    reservations = _parse_reservations(
        metadata.get(_RESERVATIONS_META_KEY) or metadata.get(_LEGACY_RESERVATIONS_META_KEY),
        plan_id=plan_id,
        specs_by_quota_id=specs_by_quota_id,
    )
    guard = get_quota_plan_service()

    if status == "success":
        if total_tokens <= 0 and cost_usd <= 0:
            return
        if request_id:
            client = await get_redis_client()
            if await client.get(f"{_PROXY_SETTLED_PREFIX}{request_id}") is not None:
                return
            if not await _acquire_once(f"{_SETTLED_PREFIX}{request_id}"):
                return
        specs = (
            [r.spec for r in reservations]
            if reservations
            else list(specs_by_quota_id.values())
        )
        settled_at = datetime.now(UTC)
        try:
            await guard.commit(
                ENTITLEMENT_NS,
                plan_id,
                specs,
                delta_tokens=total_tokens,
                delta_usd=cost_usd,
            )
            if request_id:
                await schedule_quota_plan_usage_upsert(
                    ns=ENTITLEMENT_NS,
                    plan_id=plan_id,
                    specs=specs,
                    delta_tokens=total_tokens,
                    delta_cost_usd=cost_usd,
                    request_id=request_id,
                    settled_at=settled_at,
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("entitlement_plan callback commit failed plan=%s: %s", plan_id, exc)
        return

    if not reservations:
        return
    if request_id:
        client = await get_redis_client()
        if await client.get(f"{_RELEASED_PREFIX}{request_id}") is not None:
            return
        if not await _acquire_once(f"{_RELEASED_PREFIX}{request_id}"):
            return
    try:
        await guard.release(ENTITLEMENT_NS, plan_id, reservations)
    except Exception as exc:  # pragma: no cover
        logger.warning("entitlement_plan callback release failed plan=%s: %s", plan_id, exc)


__all__ = [
    "record_proxy_entitlement_commit",
    "record_proxy_entitlement_released",
    "settle_entitlement_plan_from_callback",
]
