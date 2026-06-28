"""虚拟路由 ``retry_policy`` → LiteLLM Router 重试参数（纯函数）。"""

from __future__ import annotations

from typing import Any

from .router_model_name import (
    deployment_scope_team_id,
    encode_router_model_name,
)

# LiteLLM ``RetryPolicy`` 按异常类型配置重试次数
LITELLM_RETRY_POLICY_KEYS: frozenset[str] = frozenset(
    {
        "BadRequestErrorRetries",
        "AuthenticationErrorRetries",
        "TimeoutErrorRetries",
        "RateLimitErrorRetries",
        "ContentPolicyViolationErrorRetries",
        "InternalServerErrorRetries",
    }
)

DEFAULT_ROUTER_NUM_RETRIES = 2


def is_litellm_retry_policy(policy: dict[str, Any]) -> bool:
    return any(key in policy for key in LITELLM_RETRY_POLICY_KEYS)


def deployment_num_retries_from_policy(policy: dict[str, Any] | None) -> int | None:
    """从路由 ``retry_policy`` 提取 deployment 级 ``num_retries``（简写 ``retries`` / ``num_retries``）。"""
    if not policy:
        return None
    for key in ("num_retries", "retries"):
        raw = policy.get(key)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int) and raw >= 0:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    return None


def litellm_model_group_retry_policy(policy: dict[str, Any]) -> dict[str, Any] | None:
    """提取 LiteLLM ``RetryPolicy`` 兼容子集（去掉简写键）。"""
    if not is_litellm_retry_policy(policy):
        return None
    out = {
        key: value
        for key, value in policy.items()
        if key in LITELLM_RETRY_POLICY_KEYS and value is not None
    }
    return out or None


def routes_to_model_group_retry_policy(routes: list[Any]) -> dict[str, dict[str, Any]]:
    """将各路由的 LiteLLM 风格 ``retry_policy`` 映射为 ``model_group_retry_policy`` 键。"""
    out: dict[str, dict[str, Any]] = {}
    for route in routes:
        raw = getattr(route, "retry_policy", None)
        if not isinstance(raw, dict) or not raw:
            continue
        litellm_policy = litellm_model_group_retry_policy(raw)
        if litellm_policy is None:
            continue
        route_key = encode_router_model_name(
            deployment_scope_team_id(route),
            str(route.virtual_model),
        )
        out[route_key] = litellm_policy
    return out


__all__ = [
    "DEFAULT_ROUTER_NUM_RETRIES",
    "LITELLM_RETRY_POLICY_KEYS",
    "deployment_num_retries_from_policy",
    "is_litellm_retry_policy",
    "litellm_model_group_retry_policy",
    "routes_to_model_group_retry_policy",
]
