"""Gateway 热路径缓存统一失效入口（管理面写路径调用）。"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.application.resolve_model_cache import invalidate_for_tenant
from domains.gateway.application.route_snapshot_cache import (
    invalidate_route_snapshot_cache_for_tenant,
)
from domains.gateway.application.system_grants_cache import invalidate_grants_for_team
from domains.tenancy.application.team_cache import invalidate_team


def invalidate_gateway_read_caches_for_tenant(tenant_id: UUID) -> None:
    """模型/路由/预算/grants 变更后失效该租户相关读缓存。"""
    invalidate_for_tenant(tenant_id)
    invalidate_route_snapshot_cache_for_tenant(tenant_id)
    invalidate_team(tenant_id)


async def invalidate_gateway_budget_config_cache() -> None:
    from domains.gateway.application.budget_config_cache import invalidate_budget_config_cache

    await invalidate_budget_config_cache()


async def invalidate_gateway_grants_cache_for_team(team_id: UUID) -> None:
    await invalidate_grants_for_team(team_id)


def clear_all_gateway_read_caches_for_tests() -> None:
    from domains.gateway.application.budget_config_cache import clear_budget_config_cache_for_tests
    from domains.gateway.application.resolve_model_cache import clear_resolve_model_cache_for_tests
    from domains.gateway.application.route_snapshot_cache import (
        clear_route_snapshot_cache_for_tests,
    )
    from domains.gateway.application.system_grants_cache import clear_grants_cache_for_tests
    from domains.tenancy.application.team_cache import clear_team_cache_for_tests

    clear_budget_config_cache_for_tests()
    clear_resolve_model_cache_for_tests()
    clear_grants_cache_for_tests()
    clear_team_cache_for_tests()
    clear_route_snapshot_cache_for_tests()


__all__ = [
    "clear_all_gateway_read_caches_for_tests",
    "invalidate_gateway_budget_config_cache",
    "invalidate_gateway_grants_cache_for_team",
    "invalidate_gateway_read_caches_for_tenant",
]
