"""HTTP 头值合并（无 I/O）。"""

from __future__ import annotations


def merge_comma_separated_header_values(left: str, right: str) -> str:
    """合并逗号分隔头值（去重保序）。"""
    seen: set[str] = set()
    parts: list[str] = []
    for raw in (left, right):
        for piece in raw.split(","):
            token = piece.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            parts.append(token)
    return ",".join(parts)


def merge_anthropic_beta_values(existing: str | None, addition: str) -> str:
    return merge_comma_separated_header_values(existing or "", addition)


__all__ = ["merge_anthropic_beta_values", "merge_comma_separated_header_values"]
