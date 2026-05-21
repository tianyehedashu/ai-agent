"""Gateway 自定义 Logger：成本与 usage 提取（公开模块）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def extract_gateway_metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    """从 LiteLLM 回调 kwargs 合并 gateway_* metadata 字段。"""
    candidates: list[dict[str, Any]] = []
    for top_key in ("metadata", "litellm_metadata"):
        value = kwargs.get(top_key)
        if isinstance(value, dict):
            candidates.append(value)
    for container_key in ("litellm_params", "standard_logging_object", "optional_params"):
        container = kwargs.get(container_key)
        if isinstance(container, dict):
            inner = container.get("metadata")
            if isinstance(inner, dict):
                candidates.append(inner)

    merged: dict[str, Any] = {}
    for m in candidates:
        for k, v in m.items():
            if k not in merged or merged[k] is None:
                merged[k] = v
    return merged


def calc_upstream_cost(kwargs: dict[str, Any], response_obj: Any) -> tuple[Decimal, str]:
    from domains.gateway.application.pricing.upstream_cost_resolver import (
        resolve_upstream_cost_usd,
    )

    metadata = extract_gateway_metadata(kwargs)
    slo = kwargs.get("standard_logging_object")
    slo_dict = slo if isinstance(slo, dict) else None
    return resolve_upstream_cost_usd(
        response=response_obj,
        model=kwargs.get("model"),
        metadata=metadata,
        standard_logging=slo_dict,
    )


def extract_usage_tokens(response_obj: Any) -> tuple[int, int, int]:
    if response_obj is None:
        return 0, 0, 0
    usage = getattr(response_obj, "usage", None) or {}

    def _usage_get(key: str, default: Any = None) -> Any:
        if isinstance(usage, dict):
            return usage.get(key, default)
        return getattr(usage, key, default)

    input_tokens = int(_usage_get("prompt_tokens", 0) or 0)
    output_tokens = int(_usage_get("completion_tokens", 0) or 0)
    cached_tokens = 0
    cache_details = _usage_get("prompt_tokens_details", None)
    if isinstance(cache_details, dict):
        cached_tokens = int(cache_details.get("cached_tokens", 0) or 0)
    elif cache_details is not None:
        cached_tokens = int(getattr(cache_details, "cached_tokens", 0) or 0)
    return input_tokens, output_tokens, cached_tokens


_calc_cost = calc_upstream_cost
_extract_usage = extract_usage_tokens

__all__ = [
    "_calc_cost",
    "_extract_usage",
    "calc_upstream_cost",
    "extract_gateway_metadata",
    "extract_usage_tokens",
]
