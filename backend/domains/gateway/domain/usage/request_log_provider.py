"""请求日志 provider 解析（纯函数，供 callback 与数据回填共用）。"""

from __future__ import annotations

from domains.gateway.domain.provider.provider_inference import infer_provider_name
from domains.gateway.domain.route.router_model_name import is_router_encoded_model_name


def _non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def infer_provider_from_model_hint(value: object) -> str | None:
    """从 route/real_model 等快照推断 provider；跳过 Router 编码 model_name。"""
    stripped = _non_empty_str(value)
    if stripped is None or is_router_encoded_model_name(stripped):
        return None
    return infer_provider_name(stripped)


def infer_provider_from_model_hints(*values: object) -> str | None:
    """按顺序尝试多个模型 hint，返回首个可推断的 provider。"""
    for value in values:
        inferred = infer_provider_from_model_hint(value)
        if inferred:
            return inferred
    return None


def resolve_request_log_provider(
    *,
    metadata_provider: object = None,
    model_info_provider: object = None,
    upstream_model: str | None = None,
    response_model: str | None = None,
    model_hints: tuple[str | None, ...] = (),
) -> str | None:
    """解析写入 gateway_request_logs.provider 的值（优先级：metadata → model_info → upstream → response → hints）。"""
    for raw in (metadata_provider, model_info_provider):
        text = _non_empty_str(raw)
        if text:
            return text
    upstream = _non_empty_str(upstream_model)
    if upstream:
        return infer_provider_name(upstream)
    response = _non_empty_str(response_model)
    if response and "/" in response:
        return infer_provider_name(response)
    return infer_provider_from_model_hints(*model_hints)


__all__ = [
    "infer_provider_from_model_hint",
    "infer_provider_from_model_hints",
    "resolve_request_log_provider",
]
