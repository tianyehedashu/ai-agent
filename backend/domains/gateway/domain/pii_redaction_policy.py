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
    """对 OpenAI 兼容消息列表脱敏，返回脱敏副本与命中类别。"""
    all_hits: set[str] = set()
    out: list[dict[str, Any]] = []
    for msg in messages:
        new_msg = dict(msg)
        content = msg.get("content")
        if isinstance(content, str):
            redacted, hits = redact_text(content)
            new_msg["content"] = redacted
            all_hits.update(hits)
        elif isinstance(content, list):
            new_parts: list[Any] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    redacted, hits = redact_text(text)
                    new_part = dict(part)
                    new_part["text"] = redacted
                    new_parts.append(new_part)
                    all_hits.update(hits)
                else:
                    new_parts.append(part)
            new_msg["content"] = new_parts
        out.append(new_msg)
    return out, sorted(all_hits)


__all__ = [
    "PiiPatterns",
    "hash_original",
    "redact_messages",
    "redact_text",
]
