"""Callback 侧预算成本结算（流式以落库 cost 为最终依据，幂等）。"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.budget_platform_settlement import (
    DEFAULT_PLATFORM_PERIODS,
    commit_cached_platform_budgets,
    deserialize_budget_anchor_pins,
    resolve_budget_commit_anchor,
)
from domains.gateway.application.budget_service import BudgetService
from domains.gateway.application.budget_usage_persist import (
    PlatformBudgetUpsertItem,
    schedule_platform_budget_usage_upsert,
)
from domains.gateway.application.proxy_context import BudgetAnchorCoord
from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_row
from domains.gateway.domain.proxy_policy import budget_model_keys, budget_targets
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from libs.db.database import get_session_context
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)

_SETTLED_KEY_PREFIX = "gateway:budget:cost_settled:"
_PROXY_COST_PREFIX = "gateway:budget:proxy_cost:"
_PROXY_TOKENS_PREFIX = "gateway:budget:proxy_tokens:"
_SETTLED_TTL_SECONDS = 86400


def _to_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(value))
    return None


def _redis_decimal(raw: object) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw.decode() if isinstance(raw, bytes) else str(raw))
    except (ValueError, ArithmeticError):
        return None


def _redis_int(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw.decode() if isinstance(raw, bytes) else str(raw))
    except (TypeError, ValueError):
        return None


def _delta_after_proxy_cost(cost_usd: Decimal, proxy_cost_raw: object) -> Decimal:
    """callback 应补记的成本：proxy 已 commit 的部分扣除，未记则全额。

    仅非流式 proxy 会写 ``proxy_cost``；defer 流式 proxy 成本为 0、不写键，全额由 callback 落账。
    """
    proxy_cost = _redis_decimal(proxy_cost_raw)
    if proxy_cost is None:
        return cost_usd
    return max(Decimal("0"), cost_usd - proxy_cost)


def _delta_after_proxy_tokens(
    total_tokens: int,
    *,
    proxy_tokens_raw: object,
    proxy_settled: bool,
) -> int:
    """callback 应补记的 token，与 proxy settle_usage 协同去重（与 defer 无关）。

    - proxy 未结算该请求（两个 proxy 键皆无）→ token 全额由 callback 记账；
    - proxy 已记 token → 仅补 proxy 未覆盖的增量；
    - proxy 已结算但未单独记 token（旧 proxy 仅记 cost / 两键非原子写入时 token 写失败）
      → token 已随 proxy 结算计入，返回 0，避免在执法桶与汇总表双计。
    """
    if not proxy_settled:
        return total_tokens
    if proxy_tokens_raw is None:
        return 0
    proxy_tokens = _redis_int(proxy_tokens_raw)
    if proxy_tokens is None:
        return 0
    return max(0, total_tokens - proxy_tokens)


async def record_proxy_cost_commit(request_id: str, cost_usd: Decimal) -> None:
    """非流式 proxy 路径已 commit 的上游成本（供 callback 做 delta 修正）。"""
    if cost_usd <= 0:
        return
    client = await get_redis_client()
    key = f"{_PROXY_COST_PREFIX}{request_id}"
    await client.set(key, str(cost_usd), ex=_SETTLED_TTL_SECONDS)


async def record_proxy_usage_commit(
    request_id: str,
    *,
    cost_usd: Decimal,
    total_tokens: int,
) -> None:
    """proxy ``settle_usage`` 已结算的 cost/token（供 callback 仅补差，避免双计）。"""
    if not request_id:
        return
    client = await get_redis_client()
    if cost_usd > 0:
        await client.set(f"{_PROXY_COST_PREFIX}{request_id}", str(cost_usd), ex=_SETTLED_TTL_SECONDS)
    if total_tokens > 0:
        await client.set(
            f"{_PROXY_TOKENS_PREFIX}{request_id}",
            str(total_tokens),
            ex=_SETTLED_TTL_SECONDS,
        )


async def commit_budget_from_callback(
    *,
    metadata: dict[str, Any],
    request_id: str | None,
    cost_usd: Decimal,
    total_tokens: int,
    budget_model: str | None,
) -> None:
    """按 request_id 幂等累加预算成本/token；流式为全额，非流式仅补差。"""
    if not request_id or (cost_usd <= 0 and total_tokens <= 0):
        return

    client = await get_redis_client()
    settled_key = f"{_SETTLED_KEY_PREFIX}{request_id}"
    acquired = await client.set(settled_key, "1", nx=True, ex=_SETTLED_TTL_SECONDS)
    if not acquired:
        return

    defer = bool(metadata.get("gateway_defer_cost_settlement"))
    proxy_cost_raw = await client.get(f"{_PROXY_COST_PREFIX}{request_id}")
    proxy_tokens_raw = await client.get(f"{_PROXY_TOKENS_PREFIX}{request_id}")
    # 与 proxy settle_usage 协同去重：proxy 已记的 cost / token 一律扣减，仅补差额。
    # 任一 proxy 键存在即表示 proxy 已结算该请求（token 已随结算计入）。
    proxy_settled = proxy_cost_raw is not None or proxy_tokens_raw is not None
    delta = _delta_after_proxy_cost(cost_usd, proxy_cost_raw)
    delta_tokens = _delta_after_proxy_tokens(
        total_tokens,
        proxy_tokens_raw=proxy_tokens_raw,
        proxy_settled=proxy_settled,
    )
    if delta <= 0 and delta_tokens <= 0:
        return

    team_id = _to_uuid(metadata.get("gateway_team_id"))
    user_id = _to_uuid(metadata.get("gateway_user_id"))
    vkey_id = _to_uuid(metadata.get("gateway_vkey_id"))
    if team_id is None:
        logger.debug("budget callback skip: no team_id request_id=%s", request_id)
        return

    budget = BudgetService()
    target_items = budget_targets(tenant_id=team_id, user_id=user_id, vkey_id=vkey_id)
    periods = DEFAULT_PLATFORM_PERIODS
    pinned_anchors = deserialize_budget_anchor_pins(
        metadata.get("gateway_platform_budget_anchor_pins")
    )

    async def _load_plan(plan: object) -> dict:
        async with get_session_context() as session:
            return await BudgetRepository(session).get_many_by_plan(plan)  # type: ignore[arg-type]

    await commit_cached_platform_budgets(
        budget,
        scope_items=list(target_items),
        periods=periods,
        budget_model=budget_model,
        billing_team_id=team_id,
        delta_cost=delta,
        delta_tokens=delta_tokens,
        loader=_load_plan,
        pinned_anchors=pinned_anchors or None,
    )

    if defer and (delta > 0 or delta_tokens > 0):
        platform_upsert_items: list[PlatformBudgetUpsertItem] = []
        with suppress(Exception):
            async with get_session_context() as session:
                repo = BudgetRepository(session)
                for target_kind, target_id in target_items:
                    if target_id is None:
                        continue
                    tenant_scope = team_id if target_kind == "user" else None
                    for period in periods:
                        for mk in budget_model_keys(budget_model):
                            record = await repo.get_for(
                                target_kind,
                                target_id,
                                period,
                                model_name=mk,
                                tenant_id=tenant_scope,
                            )
                            if record is None:
                                continue
                            await repo.settle_usage(
                                record.id,
                                delta_usd=delta,
                                delta_tokens=delta_tokens,
                                delta_requests=0,
                            )
                            anchor = period_reset_anchor_from_row(
                                timezone=record.period_timezone,
                                time_minutes=record.period_reset_minutes,
                                day_of_month=record.period_reset_day,
                            )
                            coord: BudgetAnchorCoord = (
                                target_kind,
                                target_id,
                                period,
                                mk,
                                record.credential_id,
                                tenant_scope,
                            )
                            anchor = resolve_budget_commit_anchor(
                                coord,
                                config_anchor=anchor,
                                pinned_anchors=pinned_anchors or None,
                            )
                            platform_upsert_items.append(
                                PlatformBudgetUpsertItem(
                                    budget_id=record.id,
                                    period=period,
                                    period_reset_anchor=anchor,
                                )
                            )

        if request_id and platform_upsert_items:
            schedule_platform_budget_usage_upsert(
                items=platform_upsert_items,
                delta_tokens=delta_tokens,
                delta_cost_usd=delta,
                delta_requests=0,
                request_id=request_id,
                source="callback",
            )


__all__ = [
    "commit_budget_from_callback",
    "record_proxy_cost_commit",
    "record_proxy_usage_commit",
]
