"""Moonshot 端点消息规范化（纯函数，无 I/O）。

Moonshot ``/v1/chat/completions`` 对 ``messages`` 校验较严：
- ``role == "user"`` 的消息 ``content`` 不能为 ``""``、``None`` 或仅空白字符；
- 否则上游返回 ``400 - the message at position X with role 'user' must not be empty``。

本 policy 在 ``UpstreamAdapter.adapt`` 中于出站前调用，将空 ``user`` 内容替换为
最小非空占位（单个空格），避免破坏对话轮次结构。
"""

from __future__ import annotations

from typing import Any

_MOONSHOT_PROVIDER = "moonshot"


def is_moonshot_provider(provider: str | None) -> bool:
    return (provider or "").strip().lower() == _MOONSHOT_PROVIDER


def _is_empty_content(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def sanitize_messages_for_moonshot(messages: list[Any]) -> list[Any]:
    """将空 ``user`` 消息 content 替换为单个空格，其余消息原样保留。"""
    sanitized: list[Any] = []
    for msg in messages:
        if not isinstance(msg, dict):
            sanitized.append(msg)
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "user" and _is_empty_content(content):
            msg = {**msg, "content": " "}
        sanitized.append(msg)
    return sanitized


__all__ = [
    "is_moonshot_provider",
    "sanitize_messages_for_moonshot",
]
