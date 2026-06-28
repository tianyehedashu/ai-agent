"""消息清洗策略共享基础（纯函数，无 I/O）。

为各上游 provider-specific 的 message sanitize policy 提供可复用的原语：
provider 名称归一化、空 content 判断、惰性列表创建等。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def is_provider(provider: str | None, name: str) -> bool:
    """判断 ``provider`` 是否匹配给定名称（忽略大小写与前后空白）。"""
    return (provider or "").strip().lower() == name.lower()


def is_empty_content(value: Any) -> bool:
    """content 为空：``None`` 或仅空白字符串。"""
    return value is None or (isinstance(value, str) and value.strip() == "")


def sanitize_messages(
    messages: list[Any],
    *,
    placeholder: str,
    drop_non_dict: bool = False,
    should_sanitize: Callable[[dict[str, Any]], bool],
) -> list[Any]:
    """按谓词清洗消息列表：将满足 ``should_sanitize`` 的 dict 消息 ``content`` 替换为 ``placeholder``。

    Args:
        messages: 输入消息列表。
        placeholder: 替换后的 content 值。
        drop_non_dict: 为 True 时丢弃 ``None`` / 非 dict 元素；为 False 时原样保留。
        should_sanitize: 接收一个 dict 消息，返回是否需要清洗。

    Returns:
        清洗后的消息列表。若没有任何改动，直接返回原列表引用以节省内存；
        调用方不应原地修改返回的列表。
    """
    sanitized: list[Any] | None = None
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            if drop_non_dict:
                if sanitized is None:
                    sanitized = list(messages[:i])
                continue
            if sanitized is not None:
                sanitized.append(msg)
            continue

        if should_sanitize(msg):
            if sanitized is None:
                sanitized = list(messages[:i])
            sanitized.append({**msg, "content": placeholder})
        elif sanitized is not None:
            sanitized.append(msg)

    return sanitized if sanitized is not None else messages


__all__ = [
    "is_empty_content",
    "is_provider",
    "sanitize_messages",
]
