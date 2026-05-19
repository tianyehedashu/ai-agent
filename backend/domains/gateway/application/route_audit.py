"""GatewayRoute 路由完整性审计：检测 primary/fallback 引用是否有对应启用的 ``GatewayModel``。

启动期 / 测试 / 管理面诊断使用；不修复数据，仅报告。修复入口走 ``model_reference_prune``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)

if TYPE_CHECKING:
    import uuid

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


def _team_id_key(team_id: uuid.UUID | None) -> str | None:
    return str(team_id) if team_id is not None else None


def _detect_cross_team_virtual_collisions(
    routes: list,
) -> list[CrossTeamVirtualModelCollision]:
    by_vm: dict[str, set[str | None]] = {}
    for r in routes:
        vm = r.virtual_model
        by_vm.setdefault(vm, set()).add(_team_id_key(r.team_id))
    return [
        CrossTeamVirtualModelCollision(virtual_model=vm, team_ids=tuple(sorted(ids, key=str)))
        for vm, ids in sorted(by_vm.items())
        if len(ids) > 1
    ]


async def audit_gateway_routes(session: AsyncSession) -> RouteAuditReport:
    """扫描所有 enabled 路由，报告 primary/fallback 中引用了不存在或已禁用的模型名。

    判定规则：``GatewayRoute(team_id=T)`` 引用一个名字 ``N`` 时，``N`` 应当存在一行 enabled
    ``GatewayModel(team_id=T or NULL, name=N)``；同一 ``virtual_model`` 若同时被一行
    ``GatewayModel.name`` 覆盖，记录为 ``virtual_model_shadowed_by_model``（语义提示，非错误）。
    """
    routes = await GatewayRouteRepository(session).list_all_active()
    models = await GatewayModelRepository(session).list_all_active()

    by_team_name: dict[tuple[str | None, str], None] = {}
    for m in models:
        by_team_name[(_team_id_key(m.team_id), m.name)] = None

    def _name_exists(team_id: uuid.UUID | None, name: str) -> bool:
        if (_team_id_key(team_id), name) in by_team_name:
            return True
        return (None, name) in by_team_name

    issues: list[RouteReferenceIssue] = []
    shadowed: list[tuple[str | None, str]] = []
    for r in routes:
        if _name_exists(r.team_id, r.virtual_model):
            shadowed.append((_team_id_key(r.team_id), r.virtual_model))
        for field_name in _ROUTE_NAME_FIELDS:
            values = list(getattr(r, field_name) or ())
            missing = tuple(n for n in values if not _name_exists(r.team_id, n))
            if missing:
                issues.append(
                    RouteReferenceIssue(
                        team_id=_team_id_key(r.team_id),
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
