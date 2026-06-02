"""Chat / Anthropic Messages 代理入口（``/v1/chat/completions``、``/v1/messages``）。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from domains.gateway.application.anthropic_native_adapt import (
    estimate_anthropic_request_tokens,
    validate_anthropic_messages_body,
)
from domains.gateway.application.proxy_chat_pipeline import (
    apply_timing_to_metadata,
    prepare_chat_proxy_request,
)
from domains.gateway.application.proxy_response_adapter import (
    adapt_anthropic_response,
    adapt_anthropic_stream,
    adapt_response,
    adapt_stream,
)
from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback
from domains.gateway.application.proxy_router_team_metadata import (
    ensure_litellm_router_team_metadata,
)
from domains.gateway.application.proxy_timing import GatewayProxyTiming
from domains.gateway.domain.policies.anthropic_only_request_fields import (
    strip_anthropic_only_fields,
)
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.domain.upstream_call_shape_policy import (
    resolve_effective_upstream_call_shape,
)
from domains.gateway.domain.upstream_profile import UpstreamCallShape
from domains.gateway.infrastructure.router_singleton import ensure_router_deployment
from utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_use_case import ProxyUseCase


def _strip_anthropic_only_fields_for_non_anthropic_upstream(
    kwargs: dict[str, Any],
    *,
    metadata: dict[str, Any],
    model_tags: dict[str, Any] | None,
    request_id: str | None,
    client_model: str,
) -> None:
    """非 Anthropic 上游：按 domain 策略剥离 Anthropic-only 字段并写 warning 日志。"""
    upstream_provider = metadata.get("gateway_provider") if isinstance(metadata, dict) else None
    dropped = strip_anthropic_only_fields(
        kwargs,
        upstream_provider=upstream_provider if isinstance(upstream_provider, str) else None,
        model_tags=model_tags,
    )
    if dropped:
        logger.warning(
            "anthropic_messages: stripped Anthropic-only fields for non-anthropic upstream",
            extra={
                "request_id": request_id,
                "client_model": client_model,
                "upstream_provider": upstream_provider,
                "dropped_fields": dropped,
            },
        )


async def estimate_anthropic_input_tokens(body: dict[str, Any], model: str) -> int:
    try:
        from litellm import token_counter
    except ImportError:
        return estimate_anthropic_request_tokens(body)

    messages = body.get("messages")
    if not isinstance(messages, list):
        return estimate_anthropic_request_tokens(body)
    system = body.get("system")
    merged_messages: list[Any] = []
    if (isinstance(system, str) and system) or isinstance(system, list):
        merged_messages.append({"role": "system", "content": system})
    merged_messages.extend(messages)
    try:
        counted = token_counter(model=model, messages=merged_messages)
        if isinstance(counted, int) and counted > 0:
            return counted
    except Exception:
        pass
    return estimate_anthropic_request_tokens(body)


def _collect_ttfb_stream(
    original: Any,
    metadata: dict[str, Any],
    started_at: float,
) -> Any:
    """流式响应包装器：首 chunk 时记录 TTFB 到 metadata，供 CustomLogger 落库。"""
    _first = True

    async def _inner() -> Any:
        nonlocal _first
        async for chunk in original:
            if _first:
                _first = False
                ttfb = max(0, int((time.perf_counter() - started_at) * 1000))
                metadata["gateway_ttfb_ms"] = ttfb
            yield chunk

    return _inner()


class ProxyChatMixin:
    """``ProxyUseCase`` 的对话类能力入口（mixin）。"""

    async def chat_completion(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """处理 /v1/chat/completions"""
        estimate_tokens = sum(
            len(str(m.get("content", ""))) for m in (body.get("messages") or [])
        ) // 4 + int(body.get("max_tokens") or 0)
        prepared = await prepare_chat_proxy_request(
            self,
            ctx,
            body,
            estimate_tokens=estimate_tokens,
            require_model=True,
        )
        direct_started = time.perf_counter()
        use_direct = await self.litellm.should_use_internal_direct_litellm(
            ctx, prepared.model, resolved=prepared.resolved
        )
        if prepared.timings is not None:
            prepared.timings.direct_decide_ms = max(
                0, int((time.perf_counter() - direct_started) * 1000)
            )

        async def _direct() -> Any:
            return await self.litellm.direct_chat_completion(prepared.kwargs)

        async def _router() -> Any:
            encoded = str(prepared.kwargs.get("model") or "")
            ensure_litellm_router_team_metadata(prepared.kwargs, ctx.team_id)
            router = await ensure_router_deployment(self.session, encoded)
            return await router.acompletion(**prepared.kwargs)

        upstream_started = time.perf_counter()
        response = await invoke_router_with_direct_fallback(
            guard=self.guard,
            litellm=self.litellm,
            ctx=ctx,
            model=prepared.model,
            reservations=prepared.reservations,
            use_direct=use_direct,
            direct_call=_direct,
            router_call=_router,
        )
        if prepared.stream:
            response = _collect_ttfb_stream(response, prepared.metadata, upstream_started)
            if prepared.timings is not None:
                apply_timing_to_metadata(prepared.metadata, prepared.timings)
                ctx.proxy_timing = GatewayProxyTiming.from_prepare(prepared.timings)
        else:
            upstream_ms = max(0, int((time.perf_counter() - upstream_started) * 1000))
            if prepared.timings is not None:
                apply_timing_to_metadata(
                    prepared.metadata, prepared.timings, upstream_ms=upstream_ms
                )
                ctx.proxy_timing = GatewayProxyTiming.from_prepare(
                    prepared.timings, upstream_ms=upstream_ms
                )
        if prepared.stream:
            return adapt_stream(
                response,
                ctx,
                self.budget_service,
                self.entitlement_guard,
                metadata=prepared.metadata,
                downstream_custom=prepared.downstream_custom,
            )
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=prepared.metadata,
            upstream_custom=prepared.upstream_custom,
            downstream_custom=prepared.downstream_custom,
        )

    async def anthropic_messages(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | AsyncIterator[bytes]:
        """处理 ``POST /v1/messages``（LiteLLM Anthropic 原生通道）。"""
        prepared = await prepare_chat_proxy_request(
            self,
            ctx,
            body,
            estimate_tokens=estimate_anthropic_request_tokens(body),
            require_model=False,
            body_validator=validate_anthropic_messages_body,
        )
        # Anthropic-native 出站直通的实际选择落在 deployment 构造层
        # （``router_singleton._build_litellm_params``：根据 ``upstream_call_shape``
        # 把 ``model`` 改成 ``anthropic/…`` 并解析 profile 的 Anthropic-native 根）。
        # 此处只剥离非 Anthropic 上游不支持的 Anthropic-only 字段；
        # 但 ``call_shape=anthropic_native`` 时上游协议本身即 Anthropic 兼容，应保留私有字段。
        gateway_provider = (
            prepared.metadata.get("gateway_provider")
            if isinstance(prepared.metadata, dict)
            else None
        )
        profile_id = (
            prepared.metadata.get("gateway_credential_profile_id")
            if isinstance(prepared.metadata, dict)
            else None
        )
        effective_call_shape: UpstreamCallShape | None = None
        if isinstance(gateway_provider, str):
            effective_call_shape = resolve_effective_upstream_call_shape(
                model_upstream_call_shape=prepared.upstream_call_shape,
                credential_profile_id=profile_id if isinstance(profile_id, str) else None,
                provider=gateway_provider,
            )
        if effective_call_shape != UpstreamCallShape.ANTHROPIC_NATIVE:
            _strip_anthropic_only_fields_for_non_anthropic_upstream(
                prepared.kwargs,
                metadata=prepared.metadata,
                model_tags=prepared.model_tags,
                request_id=ctx.request_id,
                client_model=prepared.model,
            )
        use_direct = await self.litellm.should_use_internal_direct_litellm(
            ctx, prepared.model, resolved=prepared.resolved
        )

        async def _direct() -> Any:
            direct_kw = await self.litellm.merge_direct_deployment_litellm_params(
                prepared.kwargs, ctx, prepared.model
            )
            return await self.litellm.direct_anthropic_messages(direct_kw)

        async def _router() -> Any:
            return await self.litellm.router_anthropic_messages(prepared.kwargs)

        upstream_started = time.perf_counter()
        response = await invoke_router_with_direct_fallback(
            guard=self.guard,
            litellm=self.litellm,
            ctx=ctx,
            model=prepared.model,
            reservations=prepared.reservations,
            use_direct=use_direct,
            direct_call=_direct,
            router_call=_router,
        )
        if prepared.stream:
            response = _collect_ttfb_stream(response, prepared.metadata, upstream_started)
            if prepared.timings is not None:
                apply_timing_to_metadata(prepared.metadata, prepared.timings)
                ctx.proxy_timing = GatewayProxyTiming.from_prepare(prepared.timings)
        else:
            upstream_ms = max(0, int((time.perf_counter() - upstream_started) * 1000))
            if prepared.timings is not None:
                apply_timing_to_metadata(
                    prepared.metadata, prepared.timings, upstream_ms=upstream_ms
                )
                ctx.proxy_timing = GatewayProxyTiming.from_prepare(
                    prepared.timings, upstream_ms=upstream_ms
                )
        if prepared.stream:
            return adapt_anthropic_stream(
                response,
                ctx,
                self.budget_service,
                self.entitlement_guard,
                metadata=prepared.metadata,
                downstream_custom=prepared.downstream_custom,
            )
        return adapt_anthropic_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=prepared.metadata,
            upstream_custom=prepared.upstream_custom,
            downstream_custom=prepared.downstream_custom,
        )

    async def anthropic_count_tokens(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, int]:
        """``POST /v1/messages/count_tokens``：不计预算/限流，仅校验模型与白名单。"""
        validate_anthropic_messages_body(body)
        ctx.capability = GatewayCapability.CHAT
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self.guard.check_model(model, ctx)
        self.guard.check_capability(ctx)
        await self.guard.assert_request_capability_matches_model(ctx, model)

        input_tokens = await estimate_anthropic_input_tokens(body, model)
        return {"input_tokens": input_tokens}


__all__ = ["ProxyChatMixin", "estimate_anthropic_input_tokens"]
