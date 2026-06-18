"""注册全部 SQLAlchemy ORM 模型（脚本 / Alembic 等离线入口共用）。

应用运行时由各域按需 import；独立脚本若使用 User 等带跨域 relationship 的模型，
须先调用 ``register_all_orm_models()``，否则 mapper 初始化会因缺少关联类而失败。
"""

from __future__ import annotations


def register_all_orm_models() -> None:
    """Side-effect import：将所有 ORM 模型挂到 Declarative Base registry。"""
    # 每个域显式从自己的 infrastructure.models 模块导入，避免跨域 re-export。
    from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
    from domains.agent.infrastructure.models.listing_studio_job import ListingStudioJob  # noqa: F401
    from domains.agent.infrastructure.models.listing_studio_job_step import (  # noqa: F401
        ListingStudioJobStep,
    )
    from domains.agent.infrastructure.models.listing_studio_prompt_template import (  # noqa: F401
        ListingStudioPromptTemplate,
    )
    from domains.agent.infrastructure.models.mcp_dynamic_prompt import MCPDynamicPrompt  # noqa: F401
    from domains.agent.infrastructure.models.mcp_dynamic_tool import MCPDynamicTool  # noqa: F401
    from domains.agent.infrastructure.models.mcp_server import MCPServer  # noqa: F401
    from domains.agent.infrastructure.models.memory import Memory  # noqa: F401
    from domains.agent.infrastructure.models.message import Message  # noqa: F401
    from domains.agent.infrastructure.models.product_image_gen_task import (  # noqa: F401
        ProductImageGenTask,
    )
    from domains.agent.infrastructure.models.system_storage_config import (  # noqa: F401
        SystemStorageConfig,
    )
    from domains.agent.infrastructure.models.video_gen_task import VideoGenTask  # noqa: F401
    from domains.gateway.infrastructure.models.alert import (  # noqa: F401
        GatewayAlertEvent,
        GatewayAlertRule,
    )
    from domains.gateway.infrastructure.models.budget import GatewayBudget  # noqa: F401
    from domains.gateway.infrastructure.models.entitlement_plan import (  # noqa: F401
        EntitlementPlan,
        EntitlementPlanQuota,
    )
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel  # noqa: F401
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute  # noqa: F401
    from domains.gateway.infrastructure.models.gateway_rollup_state import (  # noqa: F401
        GatewayRollupState,
    )
    from domains.gateway.infrastructure.models.metrics_hourly import (  # noqa: F401
        GatewayMetricsHourly,
    )
    from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (  # noqa: F401
        GatewayQuotaPlanUsageBucket,
    )
    from domains.gateway.infrastructure.models.pricing_downstream import (  # noqa: F401
        DownstreamModelPricing,
    )
    from domains.gateway.infrastructure.models.pricing_upstream import (  # noqa: F401
        UpstreamModelPricing,
    )
    from domains.gateway.infrastructure.models.provider_credential import (  # noqa: F401
        ProviderCredential,
    )
    from domains.gateway.infrastructure.models.provider_quota import ProviderQuota  # noqa: F401
    from domains.gateway.infrastructure.models.request_log import GatewayRequestLog  # noqa: F401
    from domains.gateway.infrastructure.models.system_gateway import (  # noqa: F401
        SystemGatewayAlertRule,
        SystemGatewayModel,
        SystemGatewayRoute,
        SystemProviderCredential,
    )
    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey  # noqa: F401
    from domains.identity.infrastructure.models.api_key import (  # noqa: F401
        ApiKey,
        ApiKeyGatewayGrant,
        ApiKeyUsageLog,
    )
    from domains.identity.infrastructure.models.user import User  # noqa: F401
    from domains.session.infrastructure.models.session import Session  # noqa: F401
    from domains.tenancy.infrastructure.models.team import Team, TeamMember  # noqa: F401
