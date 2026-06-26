"""代理响应适配与用量结算。"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.anthropic_native_adapt import (
    anthropic_response_to_dict,
    anthropic_stream_chunk_to_bytes,
    anthropic_usage_total_tokens,
    extract_usage_from_anthropic_stream_event,
)
from domains.gateway.application.budget_platform_settlement import (
    DEFAULT_PLATFORM_PERIODS,
    commit_cached_platform_budgets,
    resolve_budget_commit_anchor,
)
from domains.gateway.application.budget_service import BudgetService
from domains.gateway.application.budget_usage_persist import (
    PlatformBudgetUpsertItem,
    schedule_platform_budget_usage_upsert,
)
from domains.gateway.application.deferred_task_runner import proxy_deferred_runner
from domains.gateway.application.entitlement_guard import EntitlementGuard
from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.application.prompt_cache_middleware import (
    apply_gateway_cache_hit_to_metadata,
)
from domains.gateway.application.proxy_context import BudgetAnchorCoord, ProxyContext
from domains.gateway.application.proxy_stream_settlement import (
    finalize_deferred_stream_settlement,
)
from domains.gateway.application.quota_plan_usage_persist import schedule_quota_plan_usage_upsert
from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_row
from domains.gateway.domain.policies.non_token_cost import response_image_count
from domains.gateway.domain.proxy_policy import (
    BudgetReservation,
    budget_model_keys,
    budget_targets,
)
from domains.gateway.domain.quota_plan import ENTITLEMENT_NS
from domains.gateway.domain.stream_utils import safe_aclose_stream
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from libs.db.database import get_session_context, prefer_background_pool
from utils.logging import get_logger

logger = get_logger(__name__)


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


async def adapt_anthropic_response(
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
    usage = data.get("usage")
    if isinstance(usage, dict):
        apply_gateway_cache_hit_to_metadata(metadata, usage)
    tokens = anthropic_usage_total_tokens(usage)
    upstream = _calc_upstream_cost(response, metadata=metadata, model=ctx.budget_model)
    from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd

    cost = proxy_budget_cost_usd(metadata, upstream)
    await schedule_settle_usage(
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
    try:
        async for chunk in stream:
            if isinstance(chunk, dict):
                usage_patch = extract_usage_from_anthropic_stream_event(chunk)
                if usage_patch is not None:
                    # Anthropic 流式 usage 分散在 message_start（input / cache）
                    # 和 message_delta（output）中；必须累积而非覆盖，
                    # 否则 cache_read_input_tokens 和 input_tokens 会丢失。
                    if last_usage is None:
                        last_usage = {}
                    last_usage.update(usage_patch)
                    apply_gateway_cache_hit_to_metadata(metadata, usage_patch)
            out = anthropic_stream_chunk_to_bytes(chunk)
            if out is not None:
                yield out
    except Exception as exc:
        logger.warning(
            "adapt_anthropic_stream upstream error: request_id=%s team_id=%s "
            "timeout=%s stream_timeout=%s ttfb_ms=%s stream=true error=%s",
            ctx.request_id,
            ctx.team_id,
            metadata.get("gateway_upstream_timeout_seconds"),
            metadata.get("gateway_upstream_stream_timeout_seconds"),
            metadata.get("gateway_ttfb_ms"),
            exc,
            exc_info=True,
        )
        raise
    finally:
        await safe_aclose_stream(stream)
    await finalize_deferred_stream_settlement(
        ctx,
        budget,
        metadata,
        last_usage,
        entitlement_guard,
    )


async def adapt_binary_response(
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
    await schedule_settle_usage(
        ctx,
        budget,
        tokens=0,
        cost=cost,
        requests=1,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
    )
    return response


async def adapt_response(
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
    images = response_image_count(response)
    await schedule_settle_usage(
        ctx,
        budget,
        tokens=tokens,
        cost=cost,
        requests=1,
        image_count=images,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
        metadata=metadata,
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
    try:
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
    except Exception as exc:
        logger.warning(
            "adapt_stream upstream error: request_id=%s team_id=%s "
            "timeout=%s stream_timeout=%s ttfb_ms=%s stream=true error=%s",
            ctx.request_id,
            ctx.team_id,
            metadata.get("gateway_upstream_timeout_seconds"),
            metadata.get("gateway_upstream_stream_timeout_seconds"),
            metadata.get("gateway_ttfb_ms"),
            exc,
            exc_info=True,
        )
        raise
    finally:
        await safe_aclose_stream(stream)
    if last_usage:
        apply_gateway_cache_hit_to_metadata(metadata, last_usage)
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
    image_count: int = 0,
    entitlement_guard: EntitlementGuard | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    # 估算预扣张数（来自 reserve 阶段）：用于 commit 时校正为响应真实张数
    estimated_platform_images = 0
    if ctx.platform_budget_preflight and ctx.platform_budget_preflight.reservations:
        for r in ctx.platform_budget_preflight.reservations:
            if r.reserved_images > 0:
                estimated_platform_images = r.reserved_images
                break
    platform_delta_images = image_count - estimated_platform_images

    estimated_entitlement_images = 0
    state = ctx.entitlement_state
    if state and state.reservations:
        for r in state.reservations:
            if r.reserved_images > 0:
                estimated_entitlement_images = r.reserved_images
                break
    entitlement_delta_images = image_count - estimated_entitlement_images

    scope_items = budget_targets(
        tenant_id=ctx.team_id,
        user_id=ctx.user_id,
        vkey_id=ctx.vkey.vkey_id if ctx.vkey else None,
    )
    periods = DEFAULT_PLATFORM_PERIODS
    pinned_anchors = (
        ctx.platform_budget_preflight.anchor_pins
        if ctx.platform_budget_preflight is not None
        else None
    )

    async def _load_plan(plan: object) -> dict:
        async with get_session_context() as session:
            return await BudgetRepository(session).get_many_by_plan(plan)  # type: ignore[arg-type]

    raw_committed_coords = await commit_cached_platform_budgets(
        budget,
        scope_items=list(scope_items),
        periods=periods,
        budget_model=ctx.budget_model,
        billing_team_id=ctx.team_id,
        delta_cost=cost,
        delta_tokens=tokens,
        loader=_load_plan,
        pinned_anchors=pinned_anchors,
        delta_images=platform_delta_images,
    )
    committed_coords = raw_committed_coords if isinstance(raw_committed_coords, set) else None
    await release_platform_budget_token_reservations(
        ctx,
        budget,
        committed_coords=committed_coords,
    )

    entitlement_committed = False
    if entitlement_guard is not None and state is not None and state.specs:
        try:
            await entitlement_guard.commit(
                state.plan_id,
                state.specs,
                delta_tokens=tokens,
                delta_usd=cost,
                delta_images=entitlement_delta_images,
            )
            entitlement_committed = True
        except Exception:
            entitlement_committed = False
        if request_id and entitlement_committed:
            with suppress(Exception):
                from domains.gateway.application.entitlement_plan_callback_settlement import (
                    record_proxy_entitlement_commit,
                )

                await record_proxy_entitlement_commit(request_id)
        if entitlement_committed and request_id and (tokens > 0 or cost > 0 or image_count > 0):
            await schedule_quota_plan_usage_upsert(
                ns=ENTITLEMENT_NS,
                plan_id=state.plan_id,
                specs=state.specs,
                delta_tokens=tokens,
                delta_cost_usd=cost,
                delta_images=image_count,
                request_id=request_id,
                settled_at=datetime.now(UTC),
            )

    if request_id and (cost > 0 or tokens > 0):
        with suppress(Exception):
            from domains.gateway.application.budget_callback_settlement import (
                record_proxy_usage_commit,
            )

            await record_proxy_usage_commit(
                request_id,
                cost_usd=cost,
                total_tokens=tokens,
            )

    platform_upsert_items: list[PlatformBudgetUpsertItem] = []
    try:
        async with get_session_context() as session:
            repo = BudgetRepository(session)
            for target_kind, target_id in scope_items:
                if target_id is None:
                    continue
                tenant_scope = ctx.team_id if target_kind == "user" else None
                for period in periods:
                    for model_key in budget_model_keys(ctx.budget_model):
                        record = await repo.get_for(
                            target_kind,
                            target_id,
                            period,
                            model_name=model_key,
                            tenant_id=tenant_scope,
                        )
                        if record is None:
                            continue
                        await repo.settle_usage(
                            record.id,
                            delta_usd=cost,
                            delta_tokens=tokens,
                            delta_requests=requests,
                            delta_images=image_count,
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
                            model_key,
                            record.credential_id,
                            tenant_scope,
                        )
                        anchor = resolve_budget_commit_anchor(
                            coord,
                            config_anchor=anchor,
                            pinned_anchors=pinned_anchors,
                        )
                        platform_upsert_items.append(
                            PlatformBudgetUpsertItem(
                                budget_id=record.id,
                                period=period,
                                period_reset_anchor=anchor,
                            )
                        )
    except Exception:
        logger.exception(
            "Platform budget PG settle failed request_id=%s team_id=%s",
            request_id,
            ctx.team_id,
        )

    if request_id and (cost > 0 or tokens > 0) and platform_upsert_items:
        await schedule_platform_budget_usage_upsert(
            items=platform_upsert_items,
            delta_tokens=tokens,
            delta_cost_usd=cost,
            delta_requests=requests,
            delta_images=image_count,
            request_id=request_id,
            source="proxy",
        )

    # 上游配额结算（直连客户端不走 LiteLLM callback，需在此处理）
    if metadata is not None and request_id:
        with suppress(Exception):
            from domains.gateway.application.provider_quota_callback_settlement import (
                settle_provider_quota_from_callback,
            )

            await settle_provider_quota_from_callback(
                metadata=metadata,
                status="success",
                cost_usd=cost,
                total_tokens=tokens,
                request_id=request_id,
                image_count=image_count,
            )


async def release_platform_budget_token_reservations(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    committed_coords: set[BudgetAnchorCoord] | None = None,
) -> None:
    """成功结算后释放 token 估算预扣，保留 request 预扣作为请求计数。"""
    state = ctx.platform_budget_preflight
    if state is None or state.token_reservations_released:
        return
    token_reservations = [r for r in state.reservations if r.reserved_tokens > 0]
    if not token_reservations:
        state.token_reservations_released = True
        return
    for reservation in token_reservations:
        if committed_coords is not None:
            coord = _budget_reservation_coord(reservation)
            if coord not in committed_coords:
                continue
        with suppress(Exception):
            await budget.release(
                target_kind=reservation.target_kind,
                target_id=reservation.target_id,
                period=reservation.period,
                budget_model_name=reservation.budget_model_name,
                credential_id=reservation.credential_id,
                tenant_id=reservation.tenant_id,
                reserved_requests=0,
                reserved_tokens=reservation.reserved_tokens,
                period_reset_anchor=reservation.period_reset_anchor,
            )
    state.token_reservations_released = True


def _budget_reservation_coord(reservation: BudgetReservation) -> BudgetAnchorCoord:
    return (
        reservation.target_kind,
        _uuid_or_none(reservation.target_id),
        reservation.period,
        reservation.budget_model_name,
        reservation.credential_id,
        reservation.tenant_id,
    )


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def schedule_settle_usage(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    tokens: int,
    cost: Decimal,
    requests: int,
    image_count: int = 0,
    entitlement_guard: EntitlementGuard | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """登记响应后结算到 **有界执行器**（不阻塞响应返回）。

    结算走 **后台连接池**，与 ``/v1/*`` 热路径物理隔离；有界队列 + 固定 worker 池消除
    无上限 fire-and-forget 占满后台池、拖垮事件循环（与 vkey 回写、桶 upsert 同策略）。
    队列满载时由 ``submit`` 背压（阻塞短超时→inline 降级），不丢结算。
    流式路径的 ``finalize_deferred_stream_settlement`` 仍在请求 task 内直接 await，
    属请求生命周期，沿用主池，不受此影响。
    """

    async def _settle() -> None:
        with prefer_background_pool():
            await settle_usage(
                ctx,
                budget,
                tokens=tokens,
                cost=cost,
                requests=requests,
                image_count=image_count,
                entitlement_guard=entitlement_guard,
                request_id=request_id,
                metadata=metadata,
            )

    with suppress(RuntimeError):
        await proxy_deferred_runner.submit(_settle)


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
    "release_platform_budget_token_reservations",
    "schedule_settle_usage",
    "settle_usage",
    "to_response_dict",
]
