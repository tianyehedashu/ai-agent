"""vkey grant team slug 映射纯规则（派发与列表共用）。"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

GrantTeamSlugRow = tuple[UUID, str]


def build_slug_by_tenant_id(rows: list[GrantTeamSlugRow]) -> dict[UUID, str]:
    """tenant_id → slug。"""
    return dict(rows)


def find_ambiguous_grant_slugs(rows: list[GrantTeamSlugRow]) -> frozenset[str]:
    """grants 集合内被多个 tenant 共用的 slug。"""
    grouped: dict[str, list[UUID]] = defaultdict(list)
    for tenant_id, slug in rows:
        grouped[slug].append(tenant_id)
    return frozenset(slug for slug, ids in grouped.items() if len(ids) > 1)


def build_unique_slug_to_tenant_id(rows: list[GrantTeamSlugRow]) -> dict[str, UUID]:
    """slug → tenant_id；homonym slug 排除（与派发 prefix lookup 对齐）。"""
    ambiguous = find_ambiguous_grant_slugs(rows)
    grouped: dict[str, list[UUID]] = defaultdict(list)
    for tenant_id, slug in rows:
        grouped[slug].append(tenant_id)
    return {
        slug: ids[0]
        for slug, ids in grouped.items()
        if slug not in ambiguous and len(ids) == 1
    }


def grant_tenant_prefix_dispatchable(
    *,
    tenant_id: UUID,
    bound_team_id: UUID,
    slug: str,
    ambiguous_slugs: frozenset[str],
) -> bool:
    """grant team 是否可安全使用 ``{slug}/model`` 前缀（与 dispatch slug_map 一致）。"""
    if tenant_id == bound_team_id:
        return True
    return slug not in ambiguous_slugs


__all__ = [
    "GrantTeamSlugRow",
    "build_slug_by_tenant_id",
    "build_unique_slug_to_tenant_id",
    "find_ambiguous_grant_slugs",
    "grant_tenant_prefix_dispatchable",
]
