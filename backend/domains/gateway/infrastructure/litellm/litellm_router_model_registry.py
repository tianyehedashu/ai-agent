"""Router deployment → LiteLLM ``model_cost`` 注册（基础设施 I/O）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.litellm.litellm_router_model_registry import (
    collect_registry_payload_from_deployments,
)
from utils.logging import get_logger

logger = get_logger(__name__)


def register_router_deployments_in_litellm_registry(
    deployments: list[dict[str, Any]],
) -> int:
    """将 Router deployment 涉及的未映射模型注册进 LiteLLM ``model_cost``。

    根治大路由池 504：未映射模型在 ``enable_pre_call_checks`` 下每请求触发
    ``This model isn't mapped yet`` 异常并被 LiteLLM 以富文本 traceback 同步打印，
    占满事件循环导致 ``/health`` 探针超时、ALB 60s 超时。注册后异常消失，且上下文
    窗口检查与成本归因得以生效。幂等：跳过已存在键，不覆盖内置映射。
    """
    if not deployments:
        return 0

    import litellm

    existing_keys = frozenset(str(k) for k in litellm.model_cost if k)
    payload = collect_registry_payload_from_deployments(
        deployments,
        existing_keys=existing_keys,
    )
    if not payload:
        return 0
    litellm.register_model(payload)
    logger.info(
        "LiteLLM router model_cost registered: %d entries (sample=%s)",
        len(payload),
        sorted(payload.keys())[:3],
    )
    return len(payload)


__all__ = ["register_router_deployments_in_litellm_registry"]
