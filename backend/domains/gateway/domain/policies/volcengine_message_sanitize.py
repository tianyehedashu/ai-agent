"""火山方舟 Coding Plan 端点消息规范化（纯函数，无 I/O）。

火山 ``/api/coding/v3`` 套餐端点对 ``messages`` 校验比标准端点更严：
- 不接受 ``null`` 元素（标准 OpenAI 允许列表含空位）；
- 不接受 ``assistant`` 消息 ``content: null`` 且无 ``tool_calls``
  （标准 OpenAI 对 tool_call 轮允许 content:null）。

本 policy 在 ``UpstreamAdapter.adapt`` 中对 volcengine 上游出站前调用，
确保 messages 数组符合 coding plan 端点要求。
"""

from __future__ import annotations

from typing import Any

_VOLCENGINE_PROVIDER = "volcengine"


def is_volcengine_provider(provider: str | None) -> bool:
    return (provider or "").strip().lower() == _VOLCENGINE_PROVIDER


def sanitize_messages_for_volcengine(
    messages: list[Any],
) -> list[Any]:
    """规范化 messages 数组，使其符合火山 coding plan 端点要求。

    处理规则：
    1. 丢弃 ``None`` / 非 dict 元素；
    2. ``assistant`` 消息 ``content`` 为 ``None`` 且无 ``tool_calls`` 时，
       将 ``content`` 归一为空字符串 ``""``；
    3. ``assistant`` 消息 ``content`` 为 ``None`` 但有 ``tool_calls`` 时，
       将 ``content`` 归一为空字符串 ``""``（coding plan 不接受 null）；
    4. 其余消息原样保留。
    """
    sanitized: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant" and msg.get("content") is None:
            msg = {**msg, "content": ""}
        sanitized.append(msg)
    return sanitized


__all__ = [
    "is_volcengine_provider",
    "sanitize_messages_for_volcengine",
]
