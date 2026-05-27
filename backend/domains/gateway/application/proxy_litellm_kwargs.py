"""代理热路径：请求体 model 解析与 LiteLLM kwargs 拼装（无 UseCase 私有方法）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.prompt_cache_middleware import PromptCacheMiddleware
from domains.gateway.application.proxy_context import ProxyContext
from domains.gateway.application.proxy_metadata_builder import (
    PreparedLitellmKwargs,
    ProxyMetadataBuilder,
)
from domains.gateway.application.upstream_adapter import UpstreamAdapter


def optional_body_model(body: dict[str, Any]) -> str | None:
    raw = body.get("model")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def kwargs_from_prepared(
    prepared: PreparedLitellmKwargs,
    *,
    upstream_adapter: UpstreamAdapter,
    prompt_cache: PromptCacheMiddleware,
) -> dict[str, Any]:
    resolved = prepared.resolved
    tags = resolved.record.tags if resolved is not None else None
    tag_dict = tags if isinstance(tags, dict) else None
    kwargs = upstream_adapter.adapt(
        prepared.kwargs,
        client_model=prepared.client_model,
        resolved=resolved,
    )
    return prompt_cache.inbound(
        kwargs,
        model=prepared.client_model or str(kwargs.get("model", "")),
        tags=tag_dict,
    )


async def prepare_litellm_invoke(
    metadata_builder: ProxyMetadataBuilder,
    ctx: ProxyContext,
    body: dict[str, Any],
    *,
    upstream_adapter: UpstreamAdapter,
    prompt_cache: PromptCacheMiddleware,
    resolved: ResolvedModelName | None = None,
) -> tuple[PreparedLitellmKwargs, dict[str, Any]]:
    """返回 metadata 准备结果与最终 LiteLLM kwargs（embedding 等需读 ``prepared.resolved``）。"""
    prepared = await metadata_builder.prepare_litellm_kwargs(ctx, body, resolved=resolved)
    kwargs = kwargs_from_prepared(
        prepared,
        upstream_adapter=upstream_adapter,
        prompt_cache=prompt_cache,
    )
    return prepared, kwargs


async def prepare_litellm_kwargs(
    metadata_builder: ProxyMetadataBuilder,
    ctx: ProxyContext,
    body: dict[str, Any],
    *,
    upstream_adapter: UpstreamAdapter,
    prompt_cache: PromptCacheMiddleware,
    resolved: ResolvedModelName | None = None,
) -> dict[str, Any]:
    _prepared, kwargs = await prepare_litellm_invoke(
        metadata_builder,
        ctx,
        body,
        upstream_adapter=upstream_adapter,
        prompt_cache=prompt_cache,
        resolved=resolved,
    )
    return kwargs


__all__ = [
    "kwargs_from_prepared",
    "optional_body_model",
    "prepare_litellm_invoke",
    "prepare_litellm_kwargs",
]
