"""Gateway 管理面变更应用服务（CQRS 写侧）。

写侧 mixin 按业务能力分散在各业务子包 management/ 下，
本文件负责组合成 GatewayManagementWriteService。
与 reads.py（读侧门面）对称。
"""

from domains.gateway.application.catalog.management.model_writes import ModelWritesMixin
from domains.gateway.application.catalog.management.probe import ProbeWritesMixin
from domains.gateway.application.credential.management.credential_writes import (
    CredentialWritesMixin,
)
from domains.gateway.application.management.write_base import (
    GatewayManagementWriteBaseMixin,
)
from domains.gateway.application.pricing.management.pricing_writes import (
    PricingWritesMixin,
)
from domains.gateway.application.quota.management.entitlement_writes import (
    EntitlementWritesMixin,
)
from domains.gateway.application.quota.management.quota_plan_delete_writes import (
    QuotaPlanQuotaDeleteWritesMixin,
)
from domains.gateway.application.quota.management.quota_rule_writes import (
    QuotaRuleWritesMixin,
)
from domains.gateway.application.quota.management.quota_usage_adjustment_writes import (
    QuotaUsageAdjustmentWritesMixin,
)
from domains.gateway.application.route.management.route_grant_writes import (
    RouteGrantWritesMixin,
)
from domains.gateway.application.route.management.route_writes import RouteWritesMixin


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
