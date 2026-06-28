"""请求日志持久化辅助：从 LiteLLM callback kwargs 提取 provider 等字段。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.litellm.litellm_deployment_attribution import (
    litellm_model_info_from_kwargs,
)
from domains.gateway.domain.usage.request_log_provider import resolve_request_log_provider


def model_info_from_kwargs(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    return litellm_model_info_from_kwargs(kwargs)


def litellm_upstream_model_from_kwargs(kwargs: dict[str, Any]) -> str | None:
    """从 Router deployment params 取 LiteLLM upstream ``model`` id（含 provider 前缀）。"""
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        model = container.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return None


def gateway_provider_for_persist(
    kwargs: dict[str, Any],
    metadata: dict[str, Any],
    *,
    response_model: str | None = None,
    model_hints: tuple[str | None, ...] = (),
) -> str | None:
    model_info = model_info_from_kwargs(kwargs)
    return resolve_request_log_provider(
        metadata_provider=metadata.get("gateway_provider"),
        model_info_provider=model_info.get("gateway_provider") if model_info else None,
        upstream_model=litellm_upstream_model_from_kwargs(kwargs),
        response_model=response_model,
        model_hints=model_hints,
    )


__all__ = [
    "gateway_provider_for_persist",
    "litellm_upstream_model_from_kwargs",
    "model_info_from_kwargs",
]
