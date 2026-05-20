"""模型默认选取策略（纯函数，与 catalog IO 解耦）。"""

from __future__ import annotations


def pick_configured_or_first_visible(
    configured_id: str,
    visible_ids: frozenset[str],
) -> str | None:
    """配置默认在可见集内则用之，否则取排序后首个可见 ID，皆无则 None。"""
    configured = configured_id.strip()
    if configured and configured in visible_ids:
        return configured
    if visible_ids:
        return sorted(visible_ids)[0]
    return None


__all__ = ["pick_configured_or_first_visible"]
