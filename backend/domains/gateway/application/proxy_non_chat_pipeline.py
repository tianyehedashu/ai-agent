"""非 Chat/Anthropic 的 /v1 代理能力（embedding / 媒体 / rerank / moderation）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.application.proxy_inbound_preflight import run_proxy_inbound_preflight
from domains.gateway.application.proxy_litellm_kwargs import optional_body_model
from domains.gateway.application.proxy_response_adapter import (
    adapt_binary_response,
    adapt_response,
    pricing_kwargs_from_litellm,
)
from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback
from domains.gateway.domain.policies.dashscope_embedding import (
    should_use_dashscope_direct_embedding,
)
from domains.gateway.domain.policies.volcengine_image import should_use_volcengine_direct_image
from domains.gateway.domain.policies.volcengine_video import should_use_volcengine_direct_video
from domains.gateway.domain.proxy_policy import BudgetReservation
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.infrastructure.router_singleton import get_router
from libs.db.session_lifecycle import rollback_open_transaction

if TYPE_CHECKING:
    from domains.gateway.application.model_or_route_resolution import ResolvedModelName
    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_use_case import ProxyUseCase


class ProxyNonChatMixin:
    """``ProxyUseCase`` 的非对话能力入口（mixin）。"""

    async def _invoke_non_chat_with_router_fallback(
        self: ProxyUseCase,
        ctx: ProxyContext,
        model: str | None,
        reservations: list[BudgetReservation],
        kwargs: dict[str, Any],
        *,
        router_call: Callable[[], Awaitable[Any]],
        direct_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        budget_model = (model or "").strip()
        use_direct = (
            await self.litellm.should_use_internal_direct_litellm(ctx, budget_model)
            if budget_model
            else False
        )
        return await invoke_router_with_direct_fallback(
            guard=self.guard,
            litellm=self.litellm,
            ctx=ctx,
            model=budget_model,
            reservations=reservations,
            use_direct=use_direct,
            direct_call=direct_call,
            router_call=router_call,
        )

    async def _run_non_chat_preflight(
        self: ProxyUseCase,
        ctx: ProxyContext,
        *,
        capability: GatewayCapability,
        model: str | None,
        require_model: bool = False,
    ) -> tuple[str | None, list[BudgetReservation], ResolvedModelName | None]:
        result = await run_proxy_inbound_preflight(
            self.guard,
            ctx,
            capability=capability,
            model=model,
            require_model=require_model,
        )
        return result.model, result.reservations, result.resolved

    async def embedding(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(body.get("model", "")).strip()
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.EMBEDDING,
            model=model,
            require_model=True,
        )
        assert budget_model is not None

        prepared, kwargs = await self.prepare_litellm_invoke(ctx, body, resolved=preflight_resolved)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        dashscope_direct = prepared.resolved is not None and should_use_dashscope_direct_embedding(
            prepared.resolved.record.provider,
            force_litellm=settings.gateway_dashscope_embedding_via_litellm,
        )
        try:
            if dashscope_direct:
                response = await self.litellm.dashscope_direct_embedding(
                    ctx,
                    prepared.client_model or budget_model,
                    kwargs,
                    real_model=prepared.resolved.record.real_model if prepared.resolved else None,
                )
            elif await self.litellm.should_use_internal_direct_litellm(ctx, budget_model):
                response = await self.litellm.direct_embedding(kwargs)
            else:
                router = await get_router(self.session)
                await rollback_open_transaction(self.session)
                response = await router.aembedding(**kwargs)
        except Exception:
            await self.guard.release_budget_reservations(reservations)
            await self.guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def image_generation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.IMAGE,
            model=optional_body_model(body),
        )
        prepared, kwargs = await self.prepare_litellm_invoke(ctx, body, resolved=preflight_resolved)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        volcengine_direct = prepared.resolved is not None and should_use_volcengine_direct_image(
            prepared.resolved.record.provider
        )
        try:
            if volcengine_direct:
                client_model = prepared.client_model or budget_model or ""
                response = await self.litellm.volcengine_direct_image_generation(
                    ctx,
                    client_model,
                    kwargs,
                )
            else:
                response = await self._invoke_non_chat_with_router_fallback(
                    ctx,
                    budget_model,
                    reservations,
                    kwargs,
                    router_call=lambda: self.litellm.router_image_generation(kwargs),
                    direct_call=lambda: self.litellm.direct_image_generation(kwargs),
                )
        except Exception:
            await self.guard.release_budget_reservations(reservations)
            await self.guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_transcription(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.AUDIO_TRANSCRIPTION,
            model=optional_body_model(body),
        )
        kwargs = await self.prepare_litellm_kwargs(ctx, body, resolved=preflight_resolved)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            response = await self._invoke_non_chat_with_router_fallback(
                ctx,
                budget_model,
                reservations,
                kwargs,
                router_call=lambda: self.litellm.router_transcription(kwargs),
                direct_call=lambda: self.litellm.direct_transcription(kwargs),
            )
        except Exception:
            await self.guard.release_budget_reservations(reservations)
            await self.guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_speech(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | bytes:
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.AUDIO_SPEECH,
            model=optional_body_model(body),
        )
        kwargs = await self.prepare_litellm_kwargs(ctx, body, resolved=preflight_resolved)
        meta, up_c, _down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            result = await self._invoke_non_chat_with_router_fallback(
                ctx,
                budget_model,
                reservations,
                kwargs,
                router_call=lambda: self.litellm.router_speech(kwargs),
                direct_call=lambda: self.litellm.direct_speech(kwargs),
            )
        except Exception:
            await self.guard.release_budget_reservations(reservations)
            await self.guard.release_entitlement_reservations(ctx)
            raise
        if isinstance(result, bytes):
            return adapt_binary_response(
                result,
                ctx,
                self.budget_service,
                self.entitlement_guard,
                metadata=meta,
                upstream_custom=up_c,
            )
        return adapt_binary_response(
            bytes(result) if result is not None else b"",
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
        )

    async def rerank(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.RERANK,
            model=optional_body_model(body),
        )
        kwargs = await self.prepare_litellm_kwargs(ctx, body, resolved=preflight_resolved)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        response = await self._invoke_non_chat_with_router_fallback(
            ctx,
            budget_model,
            reservations,
            kwargs,
            router_call=lambda: self.litellm.router_rerank(kwargs),
            direct_call=lambda: self.litellm.direct_rerank(kwargs),
        )
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def moderation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        raw_model = body.get("model")
        model = str(raw_model).strip() if raw_model is not None else ""
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.MODERATION,
            model=model or None,
        )
        kwargs = await self.prepare_litellm_kwargs(ctx, body, resolved=preflight_resolved)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        response = await self._invoke_non_chat_with_router_fallback(
            ctx,
            budget_model,
            reservations,
            kwargs,
            router_call=lambda: self.litellm.router_moderation(kwargs),
            direct_call=lambda: self.litellm.direct_moderation(kwargs),
        )
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def video_generation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(body.get("model", "")).strip()
        budget_model, reservations, preflight_resolved = await self._run_non_chat_preflight(
            ctx,
            capability=GatewayCapability.VIDEO_GENERATION,
            model=model,
            require_model=True,
        )
        assert budget_model is not None

        prepared, invoke_kwargs = await self.prepare_litellm_invoke(
            ctx, body, resolved=preflight_resolved
        )
        meta, up_c, down_c = pricing_kwargs_from_litellm(invoke_kwargs)
        volcengine_direct = prepared.resolved is not None and should_use_volcengine_direct_video(
            prepared.resolved.record.provider
        )
        try:
            if volcengine_direct:
                response = await self.litellm.volcengine_direct_video_generation(
                    ctx,
                    prepared.client_model or budget_model,
                    invoke_kwargs,
                    real_model=prepared.resolved.record.real_model if prepared.resolved else None,
                )
            else:
                response = await self._invoke_non_chat_with_router_fallback(
                    ctx,
                    budget_model,
                    reservations,
                    invoke_kwargs,
                    router_call=lambda: self.litellm.router_video_generation(invoke_kwargs),
                    direct_call=lambda: self.litellm.direct_video_generation(invoke_kwargs),
                )
        except Exception:
            await self.guard.release_budget_reservations(reservations)
            await self.guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self.budget_service,
            self.entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )


__all__ = ["ProxyNonChatMixin"]
