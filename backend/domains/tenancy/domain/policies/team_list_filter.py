"""Gateway 团队列表过滤（纯函数）。"""

from __future__ import annotations


def team_metadata_matches_search(
    *,
    name: str,
    slug: str,
    search: str | None,
) -> bool:
    """名称或 slug 包含 search（大小写不敏感）；空 search 视为匹配全部。"""
    if search is None or not search.strip():
        return True
    q = search.strip().casefold()
    return q in name.casefold() or q in slug.casefold()


__all__ = ["team_metadata_matches_search"]
