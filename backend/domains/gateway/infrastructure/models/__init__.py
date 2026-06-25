"""Gateway ORM Models

只暴露 gateway 域自己的 ORM。Team / TeamMember 权威在 ``domains.tenancy``，
按 AGENTS.md 规范请直接 ``from domains.tenancy.infrastructure.models.team import Team``，
不要走 gateway 这层 re-export（已删除）。
"""

from .alert import GatewayAlertEvent, GatewayAlertRule
from .budget import GatewayBudget
from .entitlement_plan import EntitlementPlan, EntitlementPlanQuota
from .gateway_model import GatewayModel
from .gateway_route import GatewayRoute
from .gateway_rollup_state import GatewayRollupState
from .metrics_hourly import GatewayMetricsHourly
from .pricing_downstream import DownstreamModelPricing
from .pricing_upstream import UpstreamModelPricing
from .provider_credential import ProviderCredential
from .provider_quota import ProviderQuota
from .request_log import GatewayRequestLog
from .resource_grant import GatewayResourceGrant
from .virtual_key import GatewayVirtualKey
from .virtual_key_team_grant import GatewayVirtualKeyTeamGrant

__all__ = [
    "DownstreamModelPricing",
    "EntitlementPlan",
    "EntitlementPlanQuota",
    "GatewayAlertEvent",
    "GatewayAlertRule",
    "GatewayBudget",
    "GatewayMetricsHourly",
    "GatewayRollupState",
    "GatewayModel",
    "GatewayRequestLog",
    "GatewayResourceGrant",
    "GatewayRoute",
    "GatewayVirtualKey",
    "GatewayVirtualKeyTeamGrant",
    "ProviderCredential",
    "ProviderQuota",
    "UpstreamModelPricing",
]
