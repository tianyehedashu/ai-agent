"""LiteLLM Router / 直连调用适配。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import (
    ResolvedModelName,
    resolve_model_or_route,
)
from domains.gateway.application.proxy_router_team_metadata import (
    ensure_litellm_router_team_metadata,
)
from domains.gateway.application.router_deployment_params import (
    resolve_deployment_litellm_params,
    resolve_volcengine_image_deployment,
)
from domains.gateway.domain.litellm_credential_extra_keys import litellm_api_key_param_name
from domains.gateway.domain.policies.dashscope_embedding import (
    build_dashscope_embedding_request,
)
from domains.gateway.domain.policies.volcengine_image import (
    build_volcengine_image_generation_request,
)
from domains.gateway.domain.policies.volcengine_video import (
    build_volcengine_video_create_request,
    map_volcengine_video_task_to_openai,
)
from domains.gateway.domain.proxy_policy import (
    allows_unregistered_gateway_model,
    is_reportable_upstream_proxy_exception,
)
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.infrastructure.router_singleton import (
    ensure_router_deployment,
    filter_litellm_params_for_direct_anthropic,
)
from domains.gateway.infrastructure.upstream.dashscope_embedding_client import (
    perform_dashscope_embedding,
)
from domains.gateway.infrastructure.upstream.volcengine_image_client import (
    perform_volcengine_image_generation,
)
from domains.gateway.infrastructure.upstream.volcengine_video_client import (
    perform_volcengine_video_create,
)
from libs.db.session_lifecycle import rollback_open_transaction
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.proxy_context import ProxyContext


def apply_upstream_timeout(kwargs: dict[str, Any]) -> dict[str, Any]:
    """向 LiteLLM kwargs 注入上游超时配置。"""
    timeout = settings.gateway_upstream_timeout_seconds
    stream_timeout = settings.gateway_upstream_stream_timeout_seconds
    if timeout > 0 and "timeout" not in kwargs:
        kwargs["timeout"] = timeout
    if stream_timeout > 0 and "stream_timeout" not in kwargs:
        kwargs["stream_timeout"] = stream_timeout
    return kwargs


class ProxyLiteLLMClient:
    """封装代理用例对 LiteLLM Router 与直连 API 的技术调用。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _release_session_before_upstream(self) -> None:
        await rollback_open_transaction(self._session)

    async def should_use_internal_direct_litellm(
        self,
        ctx: ProxyContext,
        model: str,
        *,
        resolved: ResolvedModelName | None = None,
    ) -> bool:
        """内部 system vkey 在没有注册 Gateway 模型/路由时可直连并继续落日志。"""
        if not allows_unregistered_gateway_model(
            vkey_is_system=ctx.vkey.is_system if ctx.vkey is not None else None,
            disable_internal_direct_litellm=settings.gateway_proxy_disable_internal_direct_litellm,
        ):
            return False
        if ctx.vkey is None or not ctx.vkey.is_system:
            return False

        model_resolved = resolved
        if model_resolved is None:
            # 跨团队聚合 vkey：仅主属 grant 时保留 personal team fallback
            enable_fb = (
                ctx.vkey is None
                or ctx.vkey.is_system
                or len(ctx.vkey.granted_team_ids) <= 1
            )
            model_resolved = await resolve_model_or_route(
                self._session, ctx.team_id, model, user_id=ctx.user_id,
                enable_personal_fallback=enable_fb,
            )
        if model_resolved is None:
            return True
        if model_resolved.route is not None:
            return False
        return not model_resolved.record.enabled

    async def direct_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        from litellm import acompletion

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
        return await acompletion(**kwargs)

    async def probe_deployment_upstream_error(
        self,
        team_id: uuid.UUID,
        client_model: str,
        *,
        capability: GatewayCapability = GatewayCapability.CHAT,
        user_id: uuid.UUID | None = None,
    ) -> Exception | None:
        """Router 聚合失败且无嵌套上游异常时，用最小请求探测真实上游错误（仅错误路径）。"""
        from domains.gateway.infrastructure.router_singleton import ensure_gateway_callbacks

        dep = await resolve_deployment_litellm_params(
            self._session,
            team_id,
            client_model,
            user_id=user_id,
        )
        if dep is None:
            return None
        ensure_gateway_callbacks()
        probe_kwargs: dict[str, Any] = dict(dep)
        apply_upstream_timeout(probe_kwargs)
        await self._release_session_before_upstream()
        try:
            await self._run_deployment_upstream_probe(probe_kwargs, capability)
        except Exception as exc:
            if is_reportable_upstream_proxy_exception(exc):
                return exc
        return None

    async def _run_deployment_upstream_probe(
        self,
        probe_kwargs: dict[str, Any],
        capability: GatewayCapability,
    ) -> None:
        """按 capability 发起最小上游探测调用。"""
        if capability == GatewayCapability.EMBEDDING:
            from litellm import aembedding

            await aembedding(**probe_kwargs, input="ping")
            return
        if capability == GatewayCapability.MODERATION:
            from litellm import amoderation

            await amoderation(**probe_kwargs, input="ping")
            return
        if capability == GatewayCapability.IMAGE:
            from litellm import aimage_generation

            await aimage_generation(**probe_kwargs, prompt="ping", n=1)
            return
        if capability == GatewayCapability.RERANK:
            from litellm import arerank

            await arerank(**probe_kwargs, query="ping", documents=["ping"])
            return
        from litellm import acompletion

        await acompletion(
            **probe_kwargs,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )

    async def direct_embedding(self, kwargs: dict[str, Any]) -> Any:
        from litellm import aembedding

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
        return await aembedding(**kwargs)

    async def router_embedding(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="aembedding",
            direct_call=lambda: self.direct_embedding(kwargs),
            kwargs=kwargs,
        )

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
        await self._release_session_before_upstream()
        return await perform_dashscope_embedding(request)

    @staticmethod
    def _merge_deployment_params_into_kwargs(
        kwargs: dict[str, Any],
        dep: dict[str, Any],
    ) -> None:
        """将 deployment litellm 参数就地 merge 到 kwargs（Router fallback / direct 共用）。"""
        dep_filtered = filter_litellm_params_for_direct_anthropic(dep)
        litellm_model = dep_filtered.pop("model", None)
        if litellm_model:
            kwargs["model"] = litellm_model
        for key, val in dep_filtered.items():
            if key not in kwargs or kwargs.get(key) in (None, ""):
                kwargs[key] = val

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
        self._merge_deployment_params_into_kwargs(merged, dep)
        return merged

    async def direct_anthropic_messages(self, kwargs: dict[str, Any]) -> Any:
        from litellm import anthropic_messages as litellm_anthropic_messages

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
        return await atranscription(**kwargs)

    async def router_transcription(self, kwargs: dict[str, Any]) -> Any:
        return await self._invoke_router_or_direct(
            router_method="atranscription",
            direct_call=lambda: self.direct_transcription(kwargs),
            kwargs=kwargs,
        )

    async def volcengine_direct_image_generation(
        self,
        ctx: ProxyContext,
        client_model: str,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """经 deployment 凭据直连火山方舟 ``/images/generations``。"""
        deployment = await resolve_volcengine_image_deployment(
            self._session, ctx.team_id, client_model, user_id=ctx.user_id
        )
        if deployment is None:
            raise ValidationError(f"no deployment for image model: {client_model}")
        dep = deployment.litellm_params
        provider = "volcengine"
        key_name = litellm_api_key_param_name(provider)
        api_key = dep.get(key_name) or dep.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValidationError("volcengine image generation requires api_key on deployment")
        prompt = kwargs.get("prompt")
        if not isinstance(prompt, str):
            raise ValidationError("prompt is required for image generation")
        try:
            request = build_volcengine_image_generation_request(
                api_key=api_key.strip(),
                api_base=dep.get("api_base") if isinstance(dep.get("api_base"), str) else None,
                image_endpoint_id=deployment.image_endpoint_id,
                prompt=prompt,
                size=kwargs.get("size") if isinstance(kwargs.get("size"), str) else None,
                n=kwargs.get("n") if isinstance(kwargs.get("n"), (int, str)) else None,
                response_format=(
                    kwargs.get("response_format")
                    if isinstance(kwargs.get("response_format"), str)
                    else None
                ),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._release_session_before_upstream()
        return await perform_volcengine_image_generation(request)

    async def volcengine_direct_video_generation(
        self,
        ctx: ProxyContext,
        client_model: str,
        kwargs: dict[str, Any],
        *,
        real_model: str | None = None,
    ) -> dict[str, Any]:
        """经 deployment 凭据直连火山方舟 ``/contents/generations/tasks``。"""
        dep = await resolve_deployment_litellm_params(
            self._session, ctx.team_id, client_model, user_id=ctx.user_id
        )
        if dep is None:
            raise ValueError(f"no deployment for video model: {client_model}")
        provider = "volcengine"
        key_name = litellm_api_key_param_name(provider)
        api_key = dep.get(key_name) or dep.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("volcengine video generation requires api_key on deployment")
        model_id = real_model or client_model
        prompt = kwargs.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required for video generation")
        request = build_volcengine_video_create_request(
            api_key=api_key.strip(),
            api_base=dep.get("api_base") if isinstance(dep.get("api_base"), str) else None,
            model_id=model_id,
            prompt=prompt.strip(),
            seconds=kwargs.get("seconds"),
        )
        await self._release_session_before_upstream()
        task_data = await perform_volcengine_video_create(request)
        return map_volcengine_video_task_to_openai(task_data, fallback_model=model_id)

    async def direct_video_generation(self, kwargs: dict[str, Any]) -> Any:
        from litellm import avideo_generation

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        apply_upstream_timeout(kwargs)
        await self._release_session_before_upstream()
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
        from domains.gateway.domain.router_model_name import decode_router_model_name
        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        apply_upstream_timeout(kwargs)
        encoded = str(kwargs.get("model") or "")
        ensure_litellm_router_team_metadata(kwargs)
        router = await ensure_router_deployment(self._session, encoded)
        router_fn = getattr(router, router_method, None)
        if not callable(router_fn):
            # Router 不支持此方法（如 aanthropic_messages），需要从 deployment
            # 提取凭据并 merge 到 kwargs，再走 direct 调用。
            # 否则 kwargs 中的 model 仍是 Router 编码名（gw/t/.../），
            # 且缺少 api_key / api_base / custom_llm_provider 等出站参数。
            decoded = decode_router_model_name(encoded)
            if decoded is not None:
                team_id, client_model = decoded
                dep = await resolve_deployment_litellm_params(
                    self._session,
                    team_id,
                    client_model,
                )
                if dep is not None:
                    self._merge_deployment_params_into_kwargs(kwargs, dep)
            await self._release_session_before_upstream()
            return await direct_call()
        await self._release_session_before_upstream()
        result = router_fn(**kwargs)
        if isinstance(result, Awaitable):
            return await result
        return result


__all__ = ["ProxyLiteLLMClient", "apply_upstream_timeout"]
