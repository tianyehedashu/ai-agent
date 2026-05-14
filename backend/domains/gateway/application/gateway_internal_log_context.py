"""内部经 GatewayBridge 调用时的请求日志详细程度（ContextVar）。

供 Agent Chat 等路径在无法直接构造 ``GatewayCallContext.store_full_messages`` 时，
通过 ``resolve_internal_store_full_messages`` + ContextVar 让 ``LLMGateway`` 注入桥接上下文。

优先级（与计划一致）：单次请求显式 > 会话 ``config.gateway_verbose_request_log`` > ``None``（沿用 vkey 默认）。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from bootstrap.config import settings

SESSION_GATEWAY_VERBOSE_KEY = "gateway_verbose_request_log"

_internal_store_full_override: ContextVar[bool | None] = ContextVar(
    "gateway_internal_store_full_override", default=None
)


def get_internal_store_full_override() -> bool | None:
    """当前异步上下文是否覆盖 ``GatewayCallContext.store_full_messages``。"""
    return _internal_store_full_override.get()


def set_internal_store_full_override(value: bool | None) -> Token[bool | None]:
    return _internal_store_full_override.set(value)


def reset_internal_store_full_override(token: Token[bool | None]) -> None:
    _internal_store_full_override.reset(token)


def resolve_internal_store_full_messages(
    *,
    request_explicit: bool | None,
    session_config: dict[str, Any] | None,
) -> bool | None:
    """解析内部 Chat 路径的 ``store_full_messages`` 覆盖值。

    Args:
        request_explicit: Chat 请求体字段；``True`` 仅在 ``gateway_allow_client_request_verbose_log`` 时生效。
        session_config: 会话 ``config``；若含键 ``gateway_verbose_request_log`` 则参与解析。
    """
    if request_explicit is True:
        if settings.gateway_allow_client_request_verbose_log:
            return True
    elif request_explicit is False:
        return False

    if isinstance(session_config, dict) and SESSION_GATEWAY_VERBOSE_KEY in session_config:
        return bool(session_config[SESSION_GATEWAY_VERBOSE_KEY])
    return None


__all__ = [
    "SESSION_GATEWAY_VERBOSE_KEY",
    "get_internal_store_full_override",
    "reset_internal_store_full_override",
    "resolve_internal_store_full_messages",
    "set_internal_store_full_override",
]
