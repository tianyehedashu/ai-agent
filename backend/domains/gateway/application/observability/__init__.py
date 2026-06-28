"""observability 子包 — Gateway 后台告警、缓存失效、延迟执行器装配。

迁移自 application/ 根目录平铺文件（M7），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 告警 job：gateway_alert_job（短事务评估 + commit 后 webhook）
- 缓存失效：gateway_cache_invalidation（热路径读缓存统一失效入口）
- 延迟执行器：deferred_task_runner（proxy_deferred_runner 单例装配，实现见 libs/concurrency）
"""

from .deferred_task_runner import proxy_deferred_runner
from .gateway_alert_job import gateway_alert_loop, run_gateway_alert_cycle
from .gateway_cache_invalidation import (
    clear_all_gateway_read_caches_for_tests,
    invalidate_gateway_budget_config_cache,
    invalidate_gateway_entitlement_config_cache,
    invalidate_gateway_grants_cache_for_team,
    invalidate_gateway_provider_plan_config_cache,
    invalidate_gateway_provider_quota_config_cache,
    invalidate_gateway_quota_rule_cache_for_team,
    invalidate_gateway_read_caches_for_tenant,
    invalidate_gateway_read_caches_for_tenant_with_grants,
    invalidate_gateway_resource_grants_cache_for_team,
)

__all__ = [
    "clear_all_gateway_read_caches_for_tests",
    "gateway_alert_loop",
    "invalidate_gateway_budget_config_cache",
    "invalidate_gateway_entitlement_config_cache",
    "invalidate_gateway_grants_cache_for_team",
    "invalidate_gateway_provider_plan_config_cache",
    "invalidate_gateway_provider_quota_config_cache",
    "invalidate_gateway_quota_rule_cache_for_team",
    "invalidate_gateway_read_caches_for_tenant",
    "invalidate_gateway_read_caches_for_tenant_with_grants",
    "invalidate_gateway_resource_grants_cache_for_team",
    "proxy_deferred_runner",
    "run_gateway_alert_cycle",
]
