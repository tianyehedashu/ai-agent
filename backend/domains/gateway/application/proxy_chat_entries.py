"""Chat / Anthropic Messages 代理入口（``/v1/chat/completions``、``/v1/messages``）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.gateway.application.anthropic_native_adapt import (
    estimate_anthropic_request_tokens,
    validate_anthropic_messages_body,
)
from domains.gateway.application.proxy_chat_pipeline import prepare_chat_proxy_request
from domains.gateway.application.proxy_response_adapter import (
    adapt_anthropic_response,
    adapt_anthropic_stream,
    adapt_response,
    adapt_stream,
)
from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.infrastructure.router_singleton import get_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_use_case import ProxyUseCase


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
        use_direct = await self.litellm.should_use_internal_direct_litellm(ctx, prepared.model)

        async def _direct() -> Any:
            return await self.litellm.direct_chat_completion(prepared.kwargs)

        async def _router() -> Any:
            router = await get_router(self.session)
            return await router.acompletion(**prepared.kwargs)

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
        use_direct = await self.litellm.should_use_internal_direct_litellm(ctx, prepared.model)

        async def _direct() -> Any:
            direct_kw = await self.litellm.merge_direct_deployment_litellm_params(
                prepared.kwargs, ctx, prepared.model
            )
            return await self.litellm.direct_anthropic_messages(direct_kw)

        async def _router() -> Any:
            return await self.litellm.router_anthropic_messages(prepared.kwargs)

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
