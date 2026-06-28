"""Moonshot 端点消息规范化（纯函数，无 I/O）。

Moonshot ``/v1/chat/completions`` 对 ``messages`` 校验较严：
- ``role == "user"`` 或 ``role == "assistant"`` 的消息 ``content`` 不能为 ``""``、
  ``None`` 或仅空白字符；
- 否则上游返回 ``400 - the message at position X with role 'user' must not be empty``
  或 ``role 'assistant' must not be empty``。

本 policy 在 ``UpstreamAdapter.adapt`` 中于出站前调用，将空 ``user`` / ``assistant``
内容替换为最小非空占位（单个空格），避免破坏对话轮次结构。
"""

from __future__ import annotations

from typing import Any

from .message_sanitize_base import (
    is_empty_content,
    is_provider,
    sanitize_messages,
)

_MOONSHOT_PROVIDER = "moonshot"
_ROLES_REQUIRING_CONTENT = frozenset({"user", "assistant"})
# Moonshot 要求 content 非空，但允许仅含空格的字符串；使用单个空格占位可保留轮次。
_PLACEHOLDER = " "


def is_moonshot_provider(provider: str | None) -> bool:
    return is_provider(provider, _MOONSHOT_PROVIDER)


def _should_sanitize(msg: dict[str, Any]) -> bool:
    role = msg.get("role")
    return (
        isinstance(role, str)
        and role in _ROLES_REQUIRING_CONTENT
        and is_empty_content(msg.get("content"))
    )


def sanitize_messages_for_moonshot(messages: list[Any]) -> list[Any]:
    """将空 ``user`` / ``assistant`` 消息 content 替换为单个空格。

    若不存在需要清洗的消息，直接返回原列表引用以节省内存；
    调用方不应原地修改返回的列表。
    """
    return sanitize_messages(
        messages,
        placeholder=_PLACEHOLDER,
        should_sanitize=_should_sanitize,
    )


__all__ = [
    "is_moonshot_provider",
    "sanitize_messages_for_moonshot",
]
