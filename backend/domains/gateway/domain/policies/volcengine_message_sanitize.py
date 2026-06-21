"""火山方舟 Coding Plan 端点消息规范化（纯函数，无 I/O）。

火山 ``/api/coding/v3`` 套餐端点对 ``messages`` 校验比标准端点更严：
- 不接受 ``null`` 元素（标准 OpenAI 允许列表含空位）；
- 不接受 ``system`` / ``user`` / ``assistant`` / ``tool`` 角色消息 ``content: null``
  或缺少 ``content`` 字段（标准 OpenAI 对 tool_call 轮允许 content:null）。

本 policy 在 ``UpstreamAdapter.adapt`` 中对 volcengine 上游出站前调用，
确保 messages 数组符合 coding plan 端点要求。
"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.policies.message_sanitize_base import (
    is_provider,
    sanitize_messages,
)

_VOLCENGINE_PROVIDER = "volcengine"
_ROLES_REQUIRING_CONTENT = frozenset({"system", "user", "assistant", "tool"})
# 火山 coding plan 端点要求 content 字段存在且不为 null；空字符串即可满足校验。
_PLACEHOLDER = ""


def is_volcengine_provider(provider: str | None) -> bool:
    return is_provider(provider, _VOLCENGINE_PROVIDER)


def _should_sanitize(msg: dict[str, Any]) -> bool:
    role = msg.get("role")
    return isinstance(role, str) and role in _ROLES_REQUIRING_CONTENT and msg.get("content") is None


def sanitize_messages_for_volcengine(
    messages: list[Any],
) -> list[Any]:
    """规范化 messages 数组，使其符合火山 coding plan 端点要求。

    处理规则：
    1. 丢弃 ``None`` / 非 dict 元素；
    2. ``system`` / ``user`` / ``assistant`` / ``tool`` 角色消息 ``content`` 为 ``None``
       或缺少 ``content`` 字段时，归一为空字符串 ``""``；
    3. 其余消息原样保留。
    """
    return sanitize_messages(
        messages,
        placeholder=_PLACEHOLDER,
        drop_non_dict=True,
        should_sanitize=_should_sanitize,
    )


__all__ = [
    "is_volcengine_provider",
    "sanitize_messages_for_volcengine",
]
