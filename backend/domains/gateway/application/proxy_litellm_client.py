"""LiteLLM Router / 直连调用适配。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import resolve_model_or_route
from domains.gateway.application.proxy_router_team_metadata import (
    ensure_litellm_router_team_metadata,
)
from domains.gateway.application.router_deployment_params import (
    resolve_deployment_litellm_params,
)
from domains.gateway.domain.litellm_credential_extra_keys import litellm_api_key_param_name
from domains.gateway.domain.policies.dashscope_embedding import (
    build_dashscope_embedding_request,
)
from domains.gateway.infrastructure.router_singleton import (
    ensure_router_deployment,
    filter_litellm_params_for_direct_anthropic,
)
from domains.gateway.infrastructure.upstream.dashscope_embedding_client import (
    perform_dashscope_embedding,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.proxy_context import ProxyContext


class ProxyLiteLLMClient:
    """封装代理用例对 LiteLLM Router 与直连 API 的技术调用。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def should_use_internal_direct_litellm(self, ctx: ProxyContext, model: str) -> bool:
        """内部 system vkey 在没有注册 Gateway 模型/路由时可直连并继续落日志。"""
        if settings.gateway_proxy_disable_internal_direct_litellm:
            return False
        if ctx.vkey is None or not ctx.vkey.is_system:
            return False

        resolved = await resolve_model_or_route(
            self._session, ctx.team_id, model, user_id=ctx.user_id
        )
        if resolved is None:
            return True
        if resolved.route is not None:
            return False
        return not resolved.record.enabled

    @staticmethod
    def is_router_model_miss(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "no deployments available",
                "no deployment",
                "no models available",
                "unable to find deployment",
                "model not found",
                "could not find model",
            )
        )

    async def direct_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        from litellm import acompletion

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await acompletion(**kwargs)

    async def direct_embedding(self, kwargs: dict[str, Any]) -> Any:
        from litellm import aembedding

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await aembedding(**kwargs)

    async def dashscope_direct_embedding(
        self,
        ctx: ProxyContext,
        client_model: str,
        kwargs: dict[str, Any],
        *,
        real_model: str | None = None,
    ) -> dict[str, Any]:
        """经 deployment 凭据直连 DashScope OpenAI 兼容 ``/embeddings``。"""
        dep = await resolve_deployment_litellm_params(
            self._session, ctx.team_id, client_model, user_id=ctx.user_id
        )
        if dep is None:
            raise ValueError(f"no deployment for embedding model: {client_model}")
        provider = "dashscope"
        key_name = litellm_api_key_param_name(provider)
        api_key = dep.get(key_name) or dep.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("dashscope embedding requires api_key on deployment")
        model_id = real_model or client_model
        request = build_dashscope_embedding_request(
            api_key=api_key.strip(),
            api_base=dep.get("api_base") if isinstance(dep.get("api_base"), str) else None,
            model_id=model_id,
            input_payload=kwargs.get("input"),
        )
        return await perform_dashscope_embedding(request)

    async def merge_direct_deployment_litellm_params(
        self,
        kwargs: dict[str, Any],
        ctx: ProxyContext,
        virtual_model: str,
    ) -> dict[str, Any]:
        """直连 LiteLLM 时注入 deployment 凭据，并将 model 换为 litellm model id。"""
        dep = await resolve_deployment_litellm_params(
            self._session, ctx.team_id, virtual_model, user_id=ctx.user_id
        )
        if dep is None:
            return kwargs
        merged = dict(kwargs)
        dep_filtered = filter_litellm_params_for_direct_anthropic(dep)
        litellm_model = dep_filtered.pop("model", None)
        if litellm_model:
            merged["model"] = litellm_model
        for key, val in dep_filtered.items():
            if key not in merged or merged.get(key) in (None, ""):
                merged[key] = val
        return merged

    async def direct_anthropic_messages(self, kwargs: dict[str, Any]) -> Any:
        from litellm import anthropic_messages as litellm_anthropic_messages

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await litellm_anthropic_messages(**kwargs)

    async def router_anthropic_messages(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="aanthropic_messages",
            direct_call=lambda: self.direct_anthropic_messages(kwargs),
            kwargs=kwargs,
        )

    async def direct_speech(self, kwargs: dict[str, Any]) -> Any:
        from litellm import aspeech

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await aspeech(**kwargs)

    async def router_speech(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="aspeech",
            direct_call=lambda: self.direct_speech(kwargs),
            kwargs=kwargs,
        )

    async def direct_rerank(self, kwargs: dict[str, Any]) -> Any:
        from litellm import arerank

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await arerank(**kwargs)

    async def router_rerank(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="arerank",
            direct_call=lambda: self.direct_rerank(kwargs),
            kwargs=kwargs,
        )

    async def direct_moderation(self, kwargs: dict[str, Any]) -> Any:
        from litellm import amoderation

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await amoderation(**kwargs)

    async def router_moderation(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="amoderation",
            direct_call=lambda: self.direct_moderation(kwargs),
            kwargs=kwargs,
        )

    async def direct_image_generation(self, kwargs: dict[str, Any]) -> Any:
        from litellm import aimage_generation

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await aimage_generation(**kwargs)

    async def router_image_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="aimage_generation",
            direct_call=lambda: self.direct_image_generation(kwargs),
            kwargs=kwargs,
        )

    async def direct_transcription(self, kwargs: dict[str, Any]) -> Any:
        from litellm import atranscription

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await atranscription(**kwargs)

    async def router_transcription(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="atranscription",
            direct_call=lambda: self.direct_transcription(kwargs),
            kwargs=kwargs,
        )

    async def direct_video_generation(self, kwargs: dict[str, Any]) -> Any:
        from litellm import avideo_generation

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await avideo_generation(**kwargs)

    async def router_video_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="avideo_generation",
            direct_call=lambda: self.direct_video_generation(kwargs),
            kwargs=kwargs,
        )

    async def _invoke_router_or_direct(
        self,
        *,
        router_method: str,
        direct_call: Callable[[], Awaitable[Any]],
        kwargs: dict[str, Any],
    ) -> Any:
        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        encoded = str(kwargs.get("model") or "")
        ensure_litellm_router_team_metadata(kwargs)
        router = await ensure_router_deployment(self._session, encoded)
        router_fn = getattr(router, router_method, None)
        if not callable(router_fn):
            return await direct_call()
        result = router_fn(**kwargs)
        if isinstance(result, Awaitable):
            return await result
        return result


__all__ = ["ProxyLiteLLMClient"]
