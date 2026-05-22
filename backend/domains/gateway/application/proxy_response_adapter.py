"""代理响应适配与用量结算。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import suppress
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from domains.gateway.application.anthropic_native_adapt import (
    anthropic_response_to_dict,
    anthropic_stream_chunk_to_bytes,
    anthropic_usage_total_tokens,
    extract_usage_from_anthropic_stream_event,
)
from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
)
from domains.gateway.application.entitlement_guard import EntitlementGuard
from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.application.prompt_cache_middleware import (
    apply_gateway_cache_hit_to_metadata,
)
from domains.gateway.application.proxy_deferred_tasks import register_proxy_deferred_task
from domains.gateway.application.proxy_stream_settlement import (
    finalize_deferred_stream_settlement,
)
from domains.gateway.domain.proxy_policy import budget_model_keys, budget_targets
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from libs.db.database import get_session_context

if TYPE_CHECKING:
    from domains.gateway.application.proxy_use_case import ProxyContext


def to_response_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "dict"):
        method = getattr(obj, attr, None)
        if callable(method):
            with suppress(Exception):
                return method()
    return {}


def pricing_kwargs_from_litellm(
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float] | None, dict[str, float] | None]:
    meta = kwargs.get("metadata")
    metadata = meta if isinstance(meta, dict) else {}
    return (
        metadata,
        upstream_custom_from_metadata(metadata),
        downstream_custom_from_metadata(metadata),
    )


def adapt_anthropic_response(
    response: Any,
    ctx: ProxyContext,
    budget: BudgetService,
    entitlement_guard: EntitlementGuard | None = None,
    *,
    metadata: dict[str, Any],
    upstream_custom: dict[str, float] | None,
    downstream_custom: dict[str, float] | None,
) -> dict[str, Any]:
    _ = upstream_custom
    data = anthropic_response_to_dict(response)
    tokens = anthropic_usage_total_tokens(data.get("usage"))
    upstream = _calc_upstream_cost(response, metadata=metadata, model=ctx.budget_model)
    from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd

    cost = proxy_budget_cost_usd(metadata, upstream)
    schedule_settle_usage(
        ctx,
        budget,
        tokens=tokens,
        cost=cost,
        requests=1,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
    )
    return enrich_anthropic_response_cost(
        data,
        source_obj=response,
        metadata=metadata,
        downstream_custom=downstream_custom,
        model=ctx.budget_model,
    )


async def adapt_anthropic_stream(
    stream: Any,
    ctx: ProxyContext,
    budget: BudgetService,
    entitlement_guard: EntitlementGuard | None = None,
    *,
    metadata: dict[str, Any],
    downstream_custom: dict[str, float] | None,
) -> AsyncIterator[bytes]:
    """Anthropic 原生 SSE 流；流末按 usage 兜底结算成本。"""
    _ = downstream_custom
    last_usage: dict[str, Any] | None = None
    async for chunk in stream:
        if isinstance(chunk, dict):
            usage_patch = extract_usage_from_anthropic_stream_event(chunk)
            if usage_patch is not None:
                last_usage = usage_patch
        out = anthropic_stream_chunk_to_bytes(chunk)
        if out is not None:
            yield out
    await finalize_deferred_stream_settlement(
        ctx,
        budget,
        metadata,
        last_usage,
        entitlement_guard,
    )


def adapt_binary_response(
    response: bytes,
    ctx: ProxyContext,
    budget: BudgetService,
    entitlement_guard: EntitlementGuard | None = None,
    *,
    metadata: dict[str, Any],
    upstream_custom: dict[str, float] | None,
) -> bytes:
    """二进制响应（如 TTS）结算：无 usage 时依赖 metadata 中的 per_request / extra 单价。"""
    _ = upstream_custom
    from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd

    upstream = _calc_upstream_cost(None, metadata=metadata, model=ctx.budget_model, requests=1)
    cost = proxy_budget_cost_usd(metadata, upstream)
    schedule_settle_usage(
        ctx,
        budget,
        tokens=0,
        cost=cost,
        requests=1,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
    )
    return response


def adapt_response(
    response: Any,
    ctx: ProxyContext,
    budget: BudgetService,
    entitlement_guard: EntitlementGuard | None = None,
    *,
    metadata: dict[str, Any],
    upstream_custom: dict[str, float] | None,
    downstream_custom: dict[str, float] | None,
) -> dict[str, Any]:
    _ = upstream_custom
    data = to_response_dict(response)
    usage = data.get("usage") or {}
    if isinstance(usage, dict):
        apply_gateway_cache_hit_to_metadata(metadata, usage)
    tokens = int(usage.get("total_tokens", 0) or 0) if isinstance(usage, dict) else 0
    from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd

    upstream = _calc_upstream_cost(response, metadata=metadata, model=ctx.budget_model)
    cost = proxy_budget_cost_usd(metadata, upstream)
    schedule_settle_usage(
        ctx,
        budget,
        tokens=tokens,
        cost=cost,
        requests=1,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
    )
    return enrich_openai_compat_response_cost(
        data,
        source_obj=response,
        metadata=metadata,
        downstream_custom=downstream_custom,
        model=ctx.budget_model,
    )


async def adapt_stream(
    stream: Any,
    ctx: ProxyContext,
    budget: BudgetService,
    entitlement_guard: EntitlementGuard | None = None,
    *,
    metadata: dict[str, Any],
    downstream_custom: dict[str, float] | None,
) -> AsyncGenerator[dict[str, Any], None]:
    """转为 SSE 友好的 dict 流；流末按 usage 兜底结算成本。"""
    last_usage: dict[str, Any] | None = None
    async for chunk in stream:
        data = to_response_dict(chunk)
        usage = data.get("usage")
        if isinstance(usage, dict):
            last_usage = usage
            apply_gateway_cache_hit_to_metadata(metadata, usage)
            if usage.get("total_tokens"):
                data = enrich_openai_compat_response_cost(
                    data,
                    source_obj=chunk,
                    metadata=metadata,
                    downstream_custom=downstream_custom,
                    model=ctx.budget_model,
                )
        yield data
    await finalize_deferred_stream_settlement(
        ctx,
        budget,
        metadata,
        last_usage,
        entitlement_guard,
    )


async def settle_usage(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    tokens: int,
    cost: Decimal,
    requests: int,
    entitlement_guard: EntitlementGuard | None = None,
    request_id: str | None = None,
) -> None:
    scope_items = budget_targets(
        tenant_id=ctx.team_id,
        user_id=ctx.user_id,
        vkey_id=ctx.vkey.vkey_id if ctx.vkey else None,
    )
    periods = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)
    model_keys = budget_model_keys(ctx.budget_model)

    for target_kind, target_id in scope_items:
        if target_id is None:
            continue
        target_id_str = str(target_id)
        for period in periods:
            for model_key in model_keys:
                with suppress(Exception):
                    await budget.commit(
                        target_kind=target_kind,
                        target_id=target_id_str,
                        period=period,
                        delta_cost=cost,
                        delta_tokens=tokens,
                        budget_model_name=model_key,
                    )

    state = ctx.entitlement_state
    if entitlement_guard is not None and state is not None and state.specs:
        with suppress(Exception):
            await entitlement_guard.commit(
                state.plan_id,
                state.specs,
                delta_tokens=tokens,
                delta_usd=cost,
            )

    if request_id and cost > 0:
        with suppress(Exception):
            from domains.gateway.application.budget_callback_settlement import (
                record_proxy_cost_commit,
            )

            await record_proxy_cost_commit(request_id, cost)

    with suppress(Exception):
        async with get_session_context() as session:
            repo = BudgetRepository(session)
            for target_kind, target_id in scope_items:
                if target_id is None:
                    continue
                for period in periods:
                    for model_key in model_keys:
                        record = await repo.get_for(
                            target_kind, target_id, period, model_name=model_key
                        )
                        if record is None:
                            continue
                        await repo.settle_usage(
                            record.id,
                            delta_usd=cost,
                            delta_tokens=tokens,
                            delta_requests=requests,
                        )


def schedule_settle_usage(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    tokens: int,
    cost: Decimal,
    requests: int,
    entitlement_guard: EntitlementGuard | None = None,
    request_id: str | None = None,
) -> None:
    """异步结算；任务登记以便测试/进程退出时收口。"""

    async def _settle() -> None:
        await settle_usage(
            ctx,
            budget,
            tokens=tokens,
            cost=cost,
            requests=requests,
            entitlement_guard=entitlement_guard,
            request_id=request_id,
        )

    with suppress(RuntimeError):
        settle_task = asyncio.create_task(_settle())
        register_proxy_deferred_task(settle_task)


def _calc_upstream_cost(
    response: Any,
    *,
    metadata: dict[str, Any],
    model: str | None,
    requests: int = 1,
) -> Decimal:
    from domains.gateway.application.pricing.upstream_cost_resolver import (
        resolve_upstream_cost_usd,
    )

    amount, _source = resolve_upstream_cost_usd(
        response=response,
        model=model,
        metadata=metadata,
        requests=requests,
    )
    return amount


def enrich_openai_compat_response_cost(
    data: dict[str, Any],
    *,
    source_obj: Any,
    metadata: dict[str, Any],
    downstream_custom: dict[str, float] | None,
    model: str | None,
) -> dict[str, Any]:
    """向 OpenAI 兼容 JSON 注入下游 response_cost（USD）。"""
    from domains.gateway.application.pricing.pricing_display_cost import (
        read_hidden_response_cost_usd,
        resolve_downstream_display_cost_usd,
    )

    if data.get("response_cost") is not None:
        return data
    hidden = read_hidden_response_cost_usd(source_obj)
    if hidden is not None and downstream_custom is None:
        return {**data, "response_cost": float(hidden)}
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return data
    if not usage.get("total_tokens") and hidden is None:
        return data
    cost = resolve_downstream_display_cost_usd(
        source_obj,
        metadata=metadata,
        model=model,
    )
    if cost <= 0:
        return data
    return {**data, "response_cost": float(cost)}


def enrich_anthropic_response_cost(
    data: dict[str, Any],
    *,
    source_obj: Any,
    metadata: dict[str, Any],
    downstream_custom: dict[str, float] | None,
    model: str | None,
) -> dict[str, Any]:
    """向 Anthropic message JSON 注入下游 response_cost（USD）。"""
    from domains.gateway.application.pricing.pricing_display_cost import (
        read_hidden_response_cost_usd,
        resolve_downstream_display_cost_usd,
    )

    if data.get("response_cost") is not None:
        return data
    hidden = read_hidden_response_cost_usd(source_obj)
    if hidden is not None and downstream_custom is None:
        return {**data, "response_cost": float(hidden)}
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return data
    if anthropic_usage_total_tokens(usage) <= 0 and hidden is None:
        return data
    cost = resolve_downstream_display_cost_usd(
        source_obj,
        metadata=metadata,
        model=model,
    )
    if cost <= 0:
        return data
    return {**data, "response_cost": float(cost)}


__all__ = [
    "adapt_anthropic_response",
    "adapt_anthropic_stream",
    "adapt_binary_response",
    "adapt_response",
    "adapt_stream",
    "enrich_anthropic_response_cost",
    "enrich_openai_compat_response_cost",
    "pricing_kwargs_from_litellm",
    "schedule_settle_usage",
    "settle_usage",
    "to_response_dict",
]
