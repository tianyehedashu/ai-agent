"""PII 脱敏规则（纯函数，无 LiteLLM / IO 依赖）。"""

from __future__ import annotations

import hashlib
import re
from typing import Any, ClassVar


class PiiPatterns:
    """常见 PII 正则"""

    PHONE = re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])")
    EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    ID_CARD = re.compile(
        r"(?<![0-9Xx])(\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])"
        r"(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx])(?![0-9Xx])"
    )
    BANK_CARD = re.compile(r"(?<![0-9])\d{13,19}(?![0-9])")
    IPV4 = re.compile(r"(?<![0-9.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![0-9.])")

    REDACTIONS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (PHONE, "[REDACTED_PHONE]"),
        (EMAIL, "[REDACTED_EMAIL]"),
        (ID_CARD, "[REDACTED_ID]"),
        (BANK_CARD, "[REDACTED_CARD]"),
        (IPV4, "[REDACTED_IP]"),
    ]


def redact_text(text: str) -> tuple[str, list[str]]:
    """对单段文本脱敏，返回 (脱敏文本, 命中类别占位符去括号小写列表)。"""
    if not text:
        return text, []
    hits: list[str] = []
    redacted = text
    for pattern, placeholder in PiiPatterns.REDACTIONS:
        if pattern.search(redacted):
            hits.append(placeholder.strip("[]").lower())
            redacted = pattern.sub(placeholder, redacted)
    seen: set[str] = set()
    unique_hits: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            unique_hits.append(h)
    return redacted, unique_hits


def hash_original(text: str) -> str:
    """对原文做 sha256，便于在日志中关联但不存原文。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def redact_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """对 OpenAI 兼容消息列表脱敏，返回脱敏副本与命中类别。

    优化：未命中 PII 的消息直接复用原 ``msg`` / ``part`` 引用，避免对大上下文场景下
    数百条消息做无意义的 ``dict(msg)`` 浅拷贝（GC 压力 + CPU 开销）。返回 ``out`` 列表
    本身仍然是新建的，命中分支的对象仍然是新分配的，外部行为与旧实现保持一致。
    """
    all_hits: set[str] = set()
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            redacted, hits = redact_text(content)
            if hits:
                new_msg = dict(msg)
                new_msg["content"] = redacted
                out.append(new_msg)
                all_hits.update(hits)
            else:
                out.append(msg)
        elif isinstance(content, list):
            modified = False
            new_parts: list[Any] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    redacted, hits = redact_text(text)
                    if hits:
                        modified = True
                        new_part = dict(part)
                        new_part["text"] = redacted
                        new_parts.append(new_part)
                        all_hits.update(hits)
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            if modified:
                new_msg = dict(msg)
                new_msg["content"] = new_parts
                out.append(new_msg)
            else:
                out.append(msg)
        else:
            out.append(msg)
    return out, sorted(all_hits)


def hash_messages_streaming(messages: list[dict[str, Any]]) -> str:
    """对消息字符串内容做流式 SHA256，等价于 ``hash_original("\\n".join(...))``。

    与 “hash_original 加头拼接” 输出**字节级一致**：按相同顺序、用 ``\\n``
    作为分隔符向 ``hashlib.sha256`` 增量喂入字节，避免一次性构造 messages 量级的临时
    大字符串。仅纳入 ``content`` 为 ``str`` 的消息，与旧实现的过滤逻辑一致。
    """
    h = hashlib.sha256()
    first = True
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        if not first:
            h.update(b"\n")
        first = False
        h.update(content.encode("utf-8"))
    return h.hexdigest()


__all__ = [
    "PiiPatterns",
    "hash_messages_streaming",
    "hash_original",
    "redact_messages",
    "redact_text",
]
