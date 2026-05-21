"""非 Chat/Anthropic 的 /v1 代理能力（embedding / 媒体 / rerank / moderation）。"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from domains.gateway.application.proxy_response_adapter import (
    adapt_response,
    pricing_kwargs_from_litellm,
    schedule_settle_usage,
)
from domains.gateway.domain.errors import EntitlementPlanExhaustedError
from domains.gateway.domain.policies.dashscope_embedding import (
    should_use_dashscope_direct_embedding,
)
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.infrastructure.router_singleton import get_router

if TYPE_CHECKING:
    from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase


class ProxyNonChatMixin:
    """``ProxyUseCase`` 的非对话能力入口（mixin）。"""

    async def embedding(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.EMBEDDING
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self._guard.check_model(model, ctx)
        self._guard.check_capability(ctx)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise

        prepared = await self._metadata_builder.prepare_litellm_kwargs(ctx, body)
        kwargs = self._kwargs_from_prepared(prepared)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        dashscope_direct = (
            prepared.resolved is not None
            and should_use_dashscope_direct_embedding(prepared.resolved.record.provider)
        )
        try:
            if dashscope_direct:
                response = await self._dashscope_direct_embedding(
                    ctx,
                    prepared.client_model or model,
                    kwargs,
                    real_model=prepared.resolved.record.real_model if prepared.resolved else None,
                )
            elif await self._should_use_internal_direct_litellm(ctx, model):
                response = await self._direct_embedding(kwargs)
            else:
                router = await get_router(self._session)
                response = await router.aembedding(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def image_generation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.IMAGE
        ctx.budget_model = self._optional_body_model(body)
        if ctx.budget_model:
            self._guard.check_model(ctx.budget_model, ctx)
        self._guard.check_capability(ctx)
        if ctx.budget_model:
            await self._guard.assert_request_capability_matches_model(ctx, ctx.budget_model)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            router = await get_router(self._session)
            response = await router.aimage_generation(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_transcription(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.AUDIO_TRANSCRIPTION
        ctx.budget_model = self._optional_body_model(body)
        self._guard.check_capability(ctx)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            router = await get_router(self._session)
            response = await router.atranscription(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_speech(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | bytes:
        ctx.capability = GatewayCapability.AUDIO_SPEECH
        ctx.budget_model = self._optional_body_model(body)
        self._guard.check_capability(ctx)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        from litellm import aspeech

        try:
            result = await aspeech(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        schedule_settle_usage(
            ctx,
            self._budget,
            tokens=0,
            cost=Decimal("0"),
            requests=1,
            entitlement_guard=self._entitlement_guard,
        )
        return result

    async def rerank(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.RERANK
        ctx.budget_model = self._optional_body_model(body)
        self._guard.check_capability(ctx)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import arerank

        try:
            response = await arerank(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def moderation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.MODERATION
        raw_model = body.get("model")
        model = str(raw_model).strip() if raw_model is not None else ""
        ctx.budget_model = model or None
        if model:
            self._guard.check_model(model, ctx)
        self._guard.check_capability(ctx)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import amoderation

        try:
            response = await amoderation(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def video_generation(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.VIDEO_GENERATION
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self._guard.check_model(model, ctx)
        self._guard.check_capability(ctx)
        await self._guard.assert_request_capability_matches_model(ctx, model)
        await self._guard.check_limits(ctx)
        reservations = await self._guard.check_budget(ctx)
        try:
            await self._guard.check_entitlement(ctx, model)
        except EntitlementPlanExhaustedError:
            await self._guard.release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import avideo_generation

        try:
            response = await avideo_generation(**kwargs)
        except Exception:
            await self._guard.release_budget_reservations(reservations)
            await self._guard.release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )


__all__ = ["ProxyNonChatMixin"]
