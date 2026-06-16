"""Callback 侧预算成本结算（流式以落库 cost 为最终依据，幂等）。"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
)
from domains.gateway.domain.proxy_policy import budget_model_keys, budget_targets
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
    proxy_key = f"{_PROXY_COST_PREFIX}{request_id}"
    proxy_tokens_key = f"{_PROXY_TOKENS_PREFIX}{request_id}"
    proxy_raw = await client.get(proxy_key)
    proxy_tokens_raw = await client.get(proxy_tokens_key)
    delta = cost_usd
    delta_tokens = total_tokens
    if not defer and proxy_raw is not None:
        with suppress(Exception):
            proxy_cost = Decimal(
                proxy_raw.decode() if isinstance(proxy_raw, bytes) else str(proxy_raw)
            )
            delta = cost_usd - proxy_cost
        if proxy_tokens_raw is not None:
            try:
                proxy_tokens = int(
                    proxy_tokens_raw.decode()
                    if isinstance(proxy_tokens_raw, bytes)
                    else str(proxy_tokens_raw)
                )
                delta_tokens = max(0, total_tokens - proxy_tokens)
            except (TypeError, ValueError):
                delta_tokens = 0
        else:
            # 同次 proxy settle_usage 已写入 token（旧部署仅记 cost 时亦成立）
            delta_tokens = 0
        if delta <= 0 and delta_tokens <= 0:
            return
        if delta < 0:
            delta = Decimal("0")

    team_id = _to_uuid(metadata.get("gateway_team_id"))
    user_id = _to_uuid(metadata.get("gateway_user_id"))
    vkey_id = _to_uuid(metadata.get("gateway_vkey_id"))
    if team_id is None:
        logger.debug("budget callback skip: no team_id request_id=%s", request_id)
        return

    budget = BudgetService()
    target_items = budget_targets(tenant_id=team_id, user_id=user_id, vkey_id=vkey_id)
    periods = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)
    model_keys = budget_model_keys(budget_model)

    for target_kind, target_id in target_items:
        if target_id is None:
            continue
        target_id_str = str(target_id)
        # 成员总量/模型护栏按团队隔离：user 维度结算到含 tenant 段的桶。
        tenant_scope = team_id if target_kind == "user" else None
        for period in periods:
            for mk in model_keys:
                with suppress(Exception):
                    await budget.commit(
                        target_kind=target_kind,
                        target_id=target_id_str,
                        period=period,
                        delta_cost=delta,
                        delta_tokens=delta_tokens,
                        budget_model_name=mk,
                        tenant_id=tenant_scope,
                    )

    if defer and (delta > 0 or delta_tokens > 0):
        with suppress(Exception):
            from domains.gateway.infrastructure.repositories.budget_repository import (
                BudgetRepository,
            )
            from libs.db.database import get_session_context

            async with get_session_context() as session:
                repo = BudgetRepository(session)
                for target_kind, target_id in target_items:
                    if target_id is None:
                        continue
                    tenant_scope = team_id if target_kind == "user" else None
                    for period in periods:
                        for mk in model_keys:
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


__all__ = [
    "commit_budget_from_callback",
    "record_proxy_cost_commit",
    "record_proxy_usage_commit",
]
