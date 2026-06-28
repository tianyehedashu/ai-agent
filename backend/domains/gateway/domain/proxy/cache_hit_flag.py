"""Prompt cache hit flag parsing rules."""

from __future__ import annotations

from typing import Any

_TRUE_STRINGS = frozenset({"1", "true", "t", "yes", "y", "on"})


def coerce_cache_hit_flag(value: Any) -> bool:
    """Return True only for explicit truthy cache-hit flags.

    Provider/LiteLLM metadata can arrive as JSON booleans, numbers, or strings.
    Python's ``bool("false")`` is True, so request-log cache metrics must not use
    generic truthiness here.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    return False


__all__ = ["coerce_cache_hit_flag"]
