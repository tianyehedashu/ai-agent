"""模型级 fallback 链路还原（纯函数，无 I/O）。

虚拟路由主模型失败后，LiteLLM Router 会按 ``fallbacks_*`` 切换到备用模型组，并在
成功响应的 ``_hidden_params.additional_headers`` 写入：

- ``x-litellm-attempted-fallbacks``：本次成功前经历的 fallback 跳数（>0 即发生切换）
- ``x-litellm-model-group``：最终命中的模型组

该模块据此（或显式 ``metadata.gateway_fallback_chain``）还原出可读的 fallback 链，
供 ``gateway_request_logs.fallback_chain`` 落库，使 failover 在日志中可见。
"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.litellm.litellm_deployment_attribution import (
    gateway_deployment_real_model,
)

from .router_model_name import decode_router_model_name

ATTEMPTED_FALLBACKS_HEADER = "x-litellm-attempted-fallbacks"
MODEL_GROUP_HEADER = "x-litellm-model-group"


def readable_model_name(value: Any) -> str | None:
    """将 Router 编码名（``gw/t/{team}/{name}`` 等）解码为客户端可读模型名。"""
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name:
        return None
    decoded = decode_router_model_name(name)
    if decoded is not None:
        return decoded[1]
    return name


def explicit_fallback_chain(metadata: dict[str, Any]) -> list[str]:
    """读取显式写入的 ``gateway_fallback_chain``（字符串或列表）。"""
    raw = metadata.get("gateway_fallback_chain") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list | tuple):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _additional_headers(response_obj: Any) -> dict[str, Any] | None:
    hidden = getattr(response_obj, "_hidden_params", None)
    if not isinstance(hidden, dict):
        return None
    headers = hidden.get("additional_headers")
    return headers if isinstance(headers, dict) else None


def attempted_fallbacks(response_obj: Any) -> int:
    headers = _additional_headers(response_obj)
    if headers is None:
        return 0
    try:
        return int(headers.get(ATTEMPTED_FALLBACKS_HEADER) or 0)
    except (TypeError, ValueError):
        return 0


def _final_model_group(response_obj: Any) -> str | None:
    headers = _additional_headers(response_obj)
    if headers is None:
        return None
    group = headers.get(MODEL_GROUP_HEADER)
    return group.strip() if isinstance(group, str) and group.strip() else None


def _append_unique(chain: list[str], name: str | None) -> None:
    if name and (not chain or chain[-1] != name):
        chain.append(name)


def build_fallback_chain(*, origin: str | None, final: str | None) -> list[str]:
    """由起点（请求的模型组）与终点（实际应答模型）拼出去重后的链。"""
    chain: list[str] = []
    _append_unique(chain, origin)
    _append_unique(chain, final)
    return chain


def resolve_fallback_chain(
    *, metadata: dict[str, Any], kwargs: dict[str, Any], response_obj: Any
) -> list[str]:
    """还原本次请求的 fallback 链；无 failover 时返回空列表。

    优先级：显式 ``gateway_fallback_chain`` > LiteLLM fallback header 推断。
    """
    explicit = explicit_fallback_chain(metadata)
    if explicit:
        return explicit
    if attempted_fallbacks(response_obj) <= 0:
        return []
    origin = readable_model_name(metadata.get("gateway_route_name")) or readable_model_name(
        kwargs.get("model")
    )
    final = (
        gateway_deployment_real_model(kwargs)
        or readable_model_name(_final_model_group(response_obj))
        or readable_model_name(kwargs.get("model"))
    )
    return build_fallback_chain(origin=origin, final=final)


def record_fallback_event_chain(
    metadata: dict[str, Any], kwargs: dict[str, Any], original_model_group: str
) -> list[str]:
    """LiteLLM fallback 事件钩子回填：把已切换的模型组追加进显式链。

    在 ``log_success_fallback_event`` / ``log_failure_fallback_event`` 中调用，
    使「主模型失败 → 备用模型」在显式链中可见（含全部失败的场景）。
    """
    origin = readable_model_name(original_model_group)
    final = gateway_deployment_real_model(kwargs) or readable_model_name(kwargs.get("model"))
    chain = explicit_fallback_chain(metadata)
    _append_unique(chain, origin)
    _append_unique(chain, final)
    metadata["gateway_fallback_chain"] = chain
    return chain


__all__ = [
    "ATTEMPTED_FALLBACKS_HEADER",
    "MODEL_GROUP_HEADER",
    "attempted_fallbacks",
    "build_fallback_chain",
    "explicit_fallback_chain",
    "readable_model_name",
    "record_fallback_event_chain",
    "resolve_fallback_chain",
]
