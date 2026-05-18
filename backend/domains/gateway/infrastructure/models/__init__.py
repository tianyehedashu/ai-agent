"""Gateway ORM Models

Team / TeamMember 权威在 domains.tenancy；此处再导出供 Alembic 与既有聚合 import 路径。
"""

from domains.tenancy.infrastructure.models.team import Team, TeamMember

from .alert import GatewayAlertEvent, GatewayAlertRule
from .budget import GatewayBudget
from .entitlement_plan import EntitlementPlan, EntitlementPlanQuota
from .gateway_model import GatewayModel
from .gateway_route import GatewayRoute
from .metrics_hourly import GatewayMetricsHourly
from .provider_credential import ProviderCredential
from .provider_plan import ProviderPlan, ProviderPlanQuota
from .request_log import GatewayRequestLog
from .virtual_key import GatewayVirtualKey

__all__ = [
    "EntitlementPlan",
    "EntitlementPlanQuota",
    "GatewayAlertEvent",
    "GatewayAlertRule",
    "GatewayBudget",
    "GatewayMetricsHourly",
    "GatewayModel",
    "GatewayRequestLog",
    "GatewayRoute",
    "GatewayVirtualKey",
    "ProviderCredential",
    "ProviderPlan",
    "ProviderPlanQuota",
    "Team",
    "TeamMember",
]
