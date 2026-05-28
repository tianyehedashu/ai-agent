"""Chat / Anthropic Messages 代理入站公共流水线（校验、预算、kwargs 准备）。

校验/限流/预算/entitlement 经 :func:`run_proxy_inbound_preflight` 完成；
LiteLLM kwargs 经 ``ProxyUseCase.prepare_litellm_invoke`` 拼装（保留 ``resolved`` / tags）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.application.proxy_inbound_preflight import run_proxy_inbound_preflight
from domains.gateway.application.proxy_timing import (
    ProxyPrepareTimings,
    timing_metadata_fields,
)
from domains.gateway.application.proxy_vision_image_urls import inline_vision_image_urls_in_kwargs
from domains.gateway.domain.proxy_policy import BudgetReservation
from domains.gateway.domain.types import GatewayCapability

if TYPE_CHECKING:
    from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase

BodyValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ChatProxyPrepared:
    """``chat_completion`` / ``anthropic_messages`` 共用准备结果。"""

    model: str
    reservations: list[BudgetReservation]
    kwargs: dict[str, Any]
    metadata: dict[str, Any]
    downstream_custom: dict[str, float] | None
    upstream_custom: dict[str, float] | None
    stream: bool
    resolved: ResolvedModelName | None = None
    model_tags: dict[str, Any] | None = None
    upstream_call_shape: str | None = None
    timings: ProxyPrepareTimings | None = None


def apply_stream_cost_defer_flag(metadata: dict[str, Any] | None, *, stream: bool) -> None:
    """流式请求标记成本由 callback / 流结束兜底结算，避免 proxy 与 callback 双计。"""
    if stream and isinstance(metadata, dict):
        metadata["gateway_defer_cost_settlement"] = True


async def prepare_chat_proxy_request(
    use_case: ProxyUseCase,
    ctx: ProxyContext,
    body: dict[str, Any],
    *,
    estimate_tokens: int,
    require_model: bool = True,
    body_validator: BodyValidator | None = None,
) -> ChatProxyPrepared:
    """校验、限流、预算预扣、拼装 LiteLLM kwargs（与具体出站 API 无关）。"""
    timings = ProxyPrepareTimings()
    if body_validator is not None:
        body_validator(body)

    model = str(body.get("model", "")).strip()
    guard_started = time.perf_counter()
    preflight = await run_proxy_inbound_preflight(
        use_case.guard,
        ctx,
        capability=GatewayCapability.CHAT,
        model=model,
        require_model=require_model,
        estimate_tokens=estimate_tokens,
    )
    timings.guard_ms = max(0, int((time.perf_counter() - guard_started) * 1000))
    assert preflight.model is not None

    prepared_litellm, kwargs = await use_case.prepare_litellm_invoke(
        ctx, body, resolved=preflight.resolved, timings=timings
    )
    vision_started = time.perf_counter()
    kwargs = await inline_vision_image_urls_in_kwargs(use_case.session, kwargs)
    timings.vision_ms = max(0, int((time.perf_counter() - vision_started) * 1000))
    meta = kwargs.get("metadata")
    metadata: dict[str, Any] = meta if isinstance(meta, dict) else {}
    stream = bool(body.get("stream"))
    apply_stream_cost_defer_flag(metadata, stream=stream)

    model_tags: dict[str, Any] | None = None
    upstream_call_shape: str | None = None
    if prepared_litellm.resolved is not None:
        record = prepared_litellm.resolved.record
        raw_tags = record.tags
        if isinstance(raw_tags, dict):
            model_tags = dict(raw_tags)
        upstream_call_shape = getattr(record, "upstream_call_shape", None)

    return ChatProxyPrepared(
        model=preflight.model,
        reservations=preflight.reservations,
        kwargs=kwargs,
        metadata=metadata,
        downstream_custom=downstream_custom_from_metadata(metadata),
        upstream_custom=upstream_custom_from_metadata(metadata),
        stream=stream,
        resolved=preflight.resolved or prepared_litellm.resolved,
        model_tags=model_tags,
        upstream_call_shape=upstream_call_shape,
        timings=timings,
    )


def apply_timing_to_metadata(
    metadata: dict[str, Any],
    timings: ProxyPrepareTimings,
    *,
    upstream_ms: int | None = None,
) -> None:
    """把分段耗时写入 kwargs metadata，供 ``gateway_request_logs`` 落库。"""
    from domains.gateway.application.proxy_timing import GatewayProxyTiming

    timing = GatewayProxyTiming.from_prepare(timings, upstream_ms=upstream_ms)
    metadata.update(timing_metadata_fields(timing))


__all__ = [
    "ChatProxyPrepared",
    "apply_stream_cost_defer_flag",
    "apply_timing_to_metadata",
    "prepare_chat_proxy_request",
]
