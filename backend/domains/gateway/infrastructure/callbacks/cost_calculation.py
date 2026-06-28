"""Gateway 自定义 Logger：成本与 usage 提取（公开模块）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _merge_gateway_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if not str(key).startswith("gateway_"):
            continue
        if key not in target or target[key] is None:
            target[key] = value


def _backfill_gateway_attribution_aliases(merged: dict[str, Any]) -> None:
    """Router ``ageneric_api_call`` 等路径常只保留 LiteLLM 标准 metadata 键。"""
    if merged.get("gateway_team_id") is None:
        team_raw = merged.get("user_api_key_team_id")
        if team_raw is not None and str(team_raw).strip():
            merged["gateway_team_id"] = team_raw
    if merged.get("gateway_user_id") is None:
        user_raw = merged.get("user_api_key_user_id")
        if user_raw is not None and str(user_raw).strip():
            merged["gateway_user_id"] = user_raw


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

    for nested_key in ("user_api_key_auth_metadata", "spend_logs_metadata", "requester_metadata"):
        nested = merged.get(nested_key)
        if isinstance(nested, dict):
            _merge_gateway_fields(merged, nested)

    _backfill_gateway_attribution_aliases(merged)
    return merged


def calc_upstream_cost(kwargs: dict[str, Any], response_obj: Any) -> tuple[Decimal, str]:
    from domains.gateway.application.upstream.upstream_cost_resolver import (
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
    """从 response_obj.usage 提取 (input_tokens, output_tokens, cached_tokens)。

    .. deprecated:: 内部委托 :func:`extract_normalized_usage`，保留签名向后兼容。
    """
    from domains.gateway.domain.usage.normalized_usage import extract_normalized_usage

    return extract_normalized_usage(response_obj).to_db_tuple()


_calc_cost = calc_upstream_cost
_extract_usage = extract_usage_tokens

__all__ = [
    "_calc_cost",
    "_extract_usage",
    "calc_upstream_cost",
    "extract_gateway_metadata",
    "extract_usage_tokens",
]
