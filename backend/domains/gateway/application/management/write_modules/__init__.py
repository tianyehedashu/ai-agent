"""Gateway 管理面写服务组合入口。"""

from __future__ import annotations

from domains.gateway.application.management.write_modules._base import (
    GatewayManagementWriteBaseMixin,
)
from domains.gateway.application.management.write_modules.credential_writes import (
    CredentialWritesMixin,
)
from domains.gateway.application.management.write_modules.entitlement_writes import (
    EntitlementWritesMixin,
)
from domains.gateway.application.management.write_modules.model_writes import (
    ModelWritesMixin,
)
from domains.gateway.application.management.write_modules.pricing_writes import (
    PricingWritesMixin,
)
from domains.gateway.application.management.write_modules.probe import ProbeWritesMixin
from domains.gateway.application.management.write_modules.quota_plan_delete_writes import (
    QuotaPlanQuotaDeleteWritesMixin,
)
from domains.gateway.application.management.write_modules.quota_rule_writes import (
    QuotaRuleWritesMixin,
)
from domains.gateway.application.management.write_modules.quota_usage_adjustment_writes import (
    QuotaUsageAdjustmentWritesMixin,
)
from domains.gateway.application.management.write_modules.route_grant_writes import (
    RouteGrantWritesMixin,
)
from domains.gateway.application.management.write_modules.route_writes import (
    RouteWritesMixin,
)


class GatewayManagementWriteService(
    ProbeWritesMixin,
    EntitlementWritesMixin,
    QuotaRuleWritesMixin,
    QuotaPlanQuotaDeleteWritesMixin,
    QuotaUsageAdjustmentWritesMixin,
    PricingWritesMixin,
    RouteGrantWritesMixin,
    RouteWritesMixin,
    ModelWritesMixin,
    CredentialWritesMixin,
    GatewayManagementWriteBaseMixin,
):
    """管理 API 状态变更，经仓储与领域服务落库。"""


__all__ = ["GatewayManagementWriteService"]
