"""Gateway 热路径缓存统一失效入口（管理面写路径调用）。"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.application.resource_grants_cache import (
    clear_resource_grants_cache_for_tests,
    invalidate_resource_grants_for_team,
)
from domains.gateway.application.resolve_model_cache import invalidate_for_tenant
from domains.gateway.application.route_snapshot_cache import (
    invalidate_route_snapshot_cache_for_tenant,
)
from domains.gateway.application.system_grants_cache import invalidate_grants_for_team
from domains.tenancy.application.team_cache import invalidate_team


def invalidate_gateway_read_caches_for_tenant(tenant_id: UUID) -> None:
    """模型/路由/预算/grants 变更后失效该租户相关读缓存。"""
    from domains.gateway.application.management.quota_rule_cache import (
        clear_local_quota_rule_cache_for_team,
    )

    clear_local_quota_rule_cache_for_team(tenant_id)
    invalidate_for_tenant(tenant_id)
    invalidate_route_snapshot_cache_for_tenant(tenant_id)
    invalidate_team(tenant_id)


async def invalidate_gateway_resource_grants_cache_for_team(team_id: UUID) -> None:
    invalidate_for_tenant(team_id)
    await invalidate_resource_grants_for_team(team_id)


def invalidate_gateway_read_caches_for_tenant_with_grants(tenant_id: UUID) -> None:
    """同步失效租户读缓存（含 resource grants L1）。"""
    invalidate_gateway_read_caches_for_tenant(tenant_id)
    from domains.gateway.application.resource_grants_cache import _LOCAL

    _LOCAL.pop(tenant_id, None)


async def invalidate_gateway_budget_config_cache() -> None:
    from domains.gateway.application.budget_config_cache import invalidate_budget_config_cache

    await invalidate_budget_config_cache()


async def invalidate_gateway_provider_quota_config_cache() -> None:
    from domains.gateway.application.provider_quota_config_cache import (
        invalidate_provider_quota_config_cache,
    )

    await invalidate_provider_quota_config_cache()


# 兼容旧导入名
invalidate_gateway_provider_plan_config_cache = invalidate_gateway_provider_quota_config_cache


async def invalidate_gateway_grants_cache_for_team(team_id: UUID) -> None:
    await invalidate_grants_for_team(team_id)


async def invalidate_gateway_entitlement_config_cache() -> None:
    from domains.gateway.application.entitlement_config_cache import (
        invalidate_entitlement_config_cache,
    )

    await invalidate_entitlement_config_cache()


async def invalidate_gateway_quota_rule_cache_for_team(team_id: UUID) -> None:
    from domains.gateway.application.management.quota_rule_cache import (
        invalidate_quota_rule_cache_for_team,
    )

    # 下游 entitlement 写路径（create/update/delete/replace_quotas/set_enabled）均汇聚到此，
    # 统一失效热路径 entitlement 配置缓存（版本号全局失效，与 provider 对称）。
    await invalidate_gateway_entitlement_config_cache()
    await invalidate_quota_rule_cache_for_team(team_id)


def clear_all_gateway_read_caches_for_tests() -> None:
    from domains.gateway.application.budget_config_cache import clear_budget_config_cache_for_tests
    from domains.gateway.application.entitlement_config_cache import (
        clear_entitlement_config_cache_for_tests,
    )
    from domains.gateway.application.provider_quota_config_cache import (
        clear_provider_quota_config_cache_for_tests,
    )
    from domains.gateway.application.resolve_model_cache import clear_resolve_model_cache_for_tests
    from domains.gateway.application.route_snapshot_cache import (
        clear_route_snapshot_cache_for_tests,
    )
    from domains.gateway.application.system_grants_cache import clear_grants_cache_for_tests
    from domains.tenancy.application.team_cache import clear_team_cache_for_tests

    clear_budget_config_cache_for_tests()
    clear_entitlement_config_cache_for_tests()
    clear_provider_quota_config_cache_for_tests()
    clear_resolve_model_cache_for_tests()
    clear_grants_cache_for_tests()
    clear_resource_grants_cache_for_tests()
    clear_team_cache_for_tests()
    clear_route_snapshot_cache_for_tests()


__all__ = [
    "clear_all_gateway_read_caches_for_tests",
    "invalidate_gateway_budget_config_cache",
    "invalidate_gateway_entitlement_config_cache",
    "invalidate_gateway_grants_cache_for_team",
    "invalidate_gateway_provider_plan_config_cache",
    "invalidate_gateway_provider_quota_config_cache",
    "invalidate_gateway_quota_rule_cache_for_team",
    "invalidate_gateway_read_caches_for_tenant",
    "invalidate_gateway_resource_grants_cache_for_team",
    "invalidate_gateway_read_caches_for_tenant_with_grants",
]
