"""GatewayRoute 路由完整性审计：检测 primary/fallback 引用是否有对应启用的 ``GatewayModel``。

启动期 / 测试 / 管理面诊断使用；不修复数据，仅报告。修复入口走 ``model_reference_prune``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.route.route_owner_slug_maps import (
    RouteOwnerSlugContext,
    build_route_owner_slug_contexts,
)
from domains.gateway.domain.route.route_model_ref import resolve_route_ref_in_registry
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class RouteReferenceIssue:
    """单条路由的失效引用。"""

    team_id: str | None
    virtual_model: str
    field: str
    missing_names: tuple[str, ...]


@dataclass(frozen=True)
class CrossTeamVirtualModelCollision:
    """不同团队使用相同 ``virtual_model`` 字面量（Router 已用编码隔离，仍建议规避）。"""

    virtual_model: str
    team_ids: tuple[str | None, ...]


@dataclass(frozen=True)
class RouteAuditReport:
    """路由审计汇总。"""

    total_routes: int
    issues: list[RouteReferenceIssue] = field(default_factory=list)
    virtual_model_shadowed_by_model: list[tuple[str | None, str]] = field(default_factory=list)
    """``GatewayRoute.virtual_model`` 同时被一行 ``GatewayModel.name`` 覆盖；调用入口冲突时模型行优先。"""
    cross_team_virtual_model_collisions: list[CrossTeamVirtualModelCollision] = field(
        default_factory=list
    )

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.issues)

    @property
    def has_warnings(self) -> bool:
        return bool(
            self.virtual_model_shadowed_by_model or self.cross_team_virtual_model_collisions
        )

    @property
    def is_clean(self) -> bool:
        """无失效引用（不含 shadowed / 跨团队同名提示）。"""
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {
            "total_routes": self.total_routes,
            "issues": [
                {
                    "team_id": i.team_id,
                    "virtual_model": i.virtual_model,
                    "field": i.field,
                    "missing_names": list(i.missing_names),
                }
                for i in self.issues
            ],
            "virtual_model_shadowed_by_model": [
                {"team_id": team_id, "virtual_model": vm}
                for team_id, vm in self.virtual_model_shadowed_by_model
            ],
            "cross_team_virtual_model_collisions": [
                {"virtual_model": c.virtual_model, "team_ids": list(c.team_ids)}
                for c in self.cross_team_virtual_model_collisions
            ],
        }


_ROUTE_NAME_FIELDS: tuple[str, ...] = (
    "primary_models",
    "fallbacks_general",
    "fallbacks_content_policy",
    "fallbacks_context_window",
)


def _scope_id_key(scope_id: uuid.UUID | None) -> str | None:
    return str(scope_id) if scope_id is not None else None


def _row_scope_id(row: object) -> uuid.UUID | None:
    tid = getattr(row, "tenant_id", None)
    return tid if isinstance(tid, uuid.UUID) else None


def _detect_cross_team_virtual_collisions(
    routes: list,
) -> list[CrossTeamVirtualModelCollision]:
    by_vm: dict[str, set[str | None]] = {}
    for r in routes:
        vm = r.virtual_model
        by_vm.setdefault(vm, set()).add(_scope_id_key(_row_scope_id(r)))
    return [
        CrossTeamVirtualModelCollision(virtual_model=vm, team_ids=tuple(sorted(ids, key=str)))
        for vm, ids in sorted(by_vm.items())
        if len(ids) > 1
    ]


async def audit_gateway_routes(session: AsyncSession) -> RouteAuditReport:
    """扫描所有 enabled 路由，报告 primary/fallback 中引用了不存在或已禁用的模型名。

    判定规则：``GatewayRoute(tenant_id=T)`` 引用一个名字 ``N`` 时，``N`` 应当存在一行 enabled
    ``GatewayModel(tenant_id=T or NULL, name=N)``；同一 ``virtual_model`` 若同时被一行
    ``GatewayModel.name`` 覆盖，记录为 ``virtual_model_shadowed_by_model``（语义提示，非错误）。
    """
    route_repo = GatewayRouteRepository(session)
    model_repo = GatewayModelRepository(session)
    routes = [
        *await route_repo.list_all_active(),
        *await route_repo.list_system(only_enabled=True),
    ]
    models = [
        *await model_repo.list_all_active(),
        *await model_repo.list_system(only_enabled=True),
    ]

    by_team_name: dict[tuple[str | None, str], object] = {}
    for m in models:
        by_team_name[(_scope_id_key(_row_scope_id(m)), m.name)] = m

    owner_ids = frozenset(
        owner_id for r in routes if (owner_id := _row_scope_id(r)) is not None
    )
    slug_contexts = await build_route_owner_slug_contexts(session, owner_ids)

    def _name_exists(scope_id: uuid.UUID | None, name: str) -> bool:
        ctx = (
            slug_contexts.get(scope_id, RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False))
            if scope_id is not None
            else RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False)
        )
        row = resolve_route_ref_in_registry(
            route_owner_tenant_id=scope_id,
            ref=name,
            by_team_name=by_team_name,
            slug_to_tenant=ctx.slug_to_tenant,
            enable_slug_prefix=ctx.enable_slug_prefix,
        )
        return row is not None

    issues: list[RouteReferenceIssue] = []
    shadowed: list[tuple[str | None, str]] = []
    for r in routes:
        route_scope = _row_scope_id(r)
        if _name_exists(route_scope, r.virtual_model):
            shadowed.append((_scope_id_key(route_scope), r.virtual_model))
        for field_name in _ROUTE_NAME_FIELDS:
            values = list(getattr(r, field_name) or ())
            missing = tuple(n for n in values if not _name_exists(route_scope, n))
            if missing:
                issues.append(
                    RouteReferenceIssue(
                        team_id=_scope_id_key(route_scope),
                        virtual_model=r.virtual_model,
                        field=field_name,
                        missing_names=missing,
                    )
                )

    return RouteAuditReport(
        total_routes=len(routes),
        issues=issues,
        virtual_model_shadowed_by_model=shadowed,
        cross_team_virtual_model_collisions=_detect_cross_team_virtual_collisions(routes),
    )


__all__ = [
    "CrossTeamVirtualModelCollision",
    "RouteAuditReport",
    "RouteReferenceIssue",
    "audit_gateway_routes",
]
