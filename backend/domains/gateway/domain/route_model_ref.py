"""个人虚拟路由 ``primary_models`` 跨团队引用编解码（纯函数）。

与 vkey 多 grant 列表 id / dispatch 前缀规则对称：

- 路由所属 personal team 的模型 → 裸别名
- 协作团队模型 → ``{team_slug}/{model_name}``
- 系统模型 → 裸别名（tenant_id=NULL）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domains.gateway.domain.vkey_grant_slug_policy import grant_tenant_prefix_dispatchable
from domains.gateway.domain.vkey_team_prefix_policy import resolve_vkey_model_prefix


class _RegistryRow(Protocol):
    name: str
    tenant_id: UUID | None


@dataclass(frozen=True, slots=True)
class RouteModelRefParsed:
    """解析 ``primary_models`` 条目后的目标 tenant 与注册别名。"""

    route_ref: str
    target_tenant_id: UUID | None
    model_name: str
    matched_slug: str | None


def encode_route_model_ref(
    *,
    route_owner_tenant_id: UUID,
    model_tenant_id: UUID | None,
    model_name: str,
    slug_by_tenant: dict[UUID, str],
    ambiguous_slugs: frozenset[str] | None = None,
) -> str:
    """计算存入 ``GatewayRoute.primary_models`` 的引用字符串。"""
    cleaned = model_name.strip()
    if not cleaned:
        return cleaned
    if model_tenant_id is None:
        return cleaned
    if model_tenant_id == route_owner_tenant_id:
        return cleaned
    slug = slug_by_tenant.get(model_tenant_id)
    if slug is None:
        msg = f"missing team slug for tenant_id={model_tenant_id}"
        raise KeyError(msg)
    if ambiguous_slugs is not None and slug in ambiguous_slugs:
        msg = f"ambiguous team slug {slug!r} cannot prefix route model ref"
        raise ValueError(msg)
    return f"{slug}/{cleaned}"


def parse_route_model_ref(
    *,
    route_owner_tenant_id: UUID,
    ref: str,
    slug_to_tenant: dict[str, UUID],
) -> RouteModelRefParsed:
    """解析 ``primary_models`` 条目；无 ``/`` 或 slug 未命中时视为路由所属 tenant。"""
    cleaned = ref.strip()
    if not cleaned:
        return RouteModelRefParsed(
            route_ref=cleaned,
            target_tenant_id=route_owner_tenant_id,
            model_name=cleaned,
            matched_slug=None,
        )
    dispatch = resolve_vkey_model_prefix(
        bound_team_id=route_owner_tenant_id,
        raw_model=cleaned,
        slug_map=slug_to_tenant,
        strict=False,
    )
    if dispatch.matched_slug is not None:
        return RouteModelRefParsed(
            route_ref=cleaned,
            target_tenant_id=dispatch.effective_team_id,
            model_name=dispatch.real_model_name,
            matched_slug=dispatch.matched_slug,
        )
    return RouteModelRefParsed(
        route_ref=cleaned,
        target_tenant_id=route_owner_tenant_id,
        model_name=cleaned,
        matched_slug=None,
    )


def registry_lookup_key(tenant_id: UUID | None) -> str | None:
    """``by_team_name`` 字典 scope key（与 router_singleton 一致）。"""
    return str(tenant_id) if tenant_id is not None else None


def resolve_parsed_ref_in_registry(
    parsed: RouteModelRefParsed,
    by_team_name: dict[tuple[str | None, str], _RegistryRow],
) -> _RegistryRow | None:
    """在预建 registry 索引中查找解析后的模型行。"""
    scope_key = registry_lookup_key(parsed.target_tenant_id)
    row = by_team_name.get((scope_key, parsed.model_name))
    if row is not None:
        return row
    if parsed.matched_slug is not None:
        return None
    if parsed.target_tenant_id is not None:
        return by_team_name.get((None, parsed.model_name))
    return None


def resolve_route_ref_in_registry(
    *,
    route_owner_tenant_id: UUID | None,
    ref: str,
    by_team_name: dict[tuple[str | None, str], _RegistryRow],
    slug_to_tenant: dict[str, UUID],
    enable_slug_prefix: bool = True,
) -> _RegistryRow | None:
    """解析 ``GatewayRoute`` 引用名并在 registry 索引中查找模型行。"""
    if route_owner_tenant_id is None:
        return by_team_name.get((None, ref.strip()))
    cleaned = ref.strip()
    if enable_slug_prefix:
        parsed = parse_route_model_ref(
            route_owner_tenant_id=route_owner_tenant_id,
            ref=ref,
            slug_to_tenant=slug_to_tenant,
        )
    else:
        parsed = RouteModelRefParsed(
            route_ref=cleaned,
            target_tenant_id=route_owner_tenant_id,
            model_name=cleaned,
            matched_slug=None,
        )
    return resolve_parsed_ref_in_registry(parsed, by_team_name)


def route_ref_prefix_dispatchable(
    *,
    route_owner_tenant_id: UUID,
    model_tenant_id: UUID | None,
    slug: str | None,
    ambiguous_slugs: frozenset[str],
) -> bool:
    """协作团队模型是否可安全写入带 slug 前缀的 route_ref。"""
    if model_tenant_id is None or model_tenant_id == route_owner_tenant_id:
        return True
    if slug is None:
        return False
    return grant_tenant_prefix_dispatchable(
        tenant_id=model_tenant_id,
        bound_team_id=route_owner_tenant_id,
        slug=slug,
        ambiguous_slugs=ambiguous_slugs,
    )


__all__ = [
    "RouteModelRefParsed",
    "encode_route_model_ref",
    "parse_route_model_ref",
    "registry_lookup_key",
    "resolve_parsed_ref_in_registry",
    "resolve_route_ref_in_registry",
    "route_ref_prefix_dispatchable",
]
