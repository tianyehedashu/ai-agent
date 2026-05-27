"""
Gateway Domain Types - 领域类型定义

包含枚举、值对象与领域 DTO。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from domains.tenancy.domain.management_context import ManagementTeamContext

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

# =============================================================================
# 枚举
# =============================================================================


class TeamKind(str, Enum):
    """团队类型"""

    PERSONAL = "personal"  # 个人团队（用户注册时自动创建）
    SHARED = "shared"  # 共享团队


class TeamRole(str, Enum):
    """团队成员角色"""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CredentialScope(str, Enum):
    """凭据归属作用域（API / 日志展示与部分写入别名）。

    存储形态（``provider_credentials``）：
    - 系统：``system_provider_credentials`` 表；API 展示 ``system``
    - 租户：``tenant_id`` 非空且 ``scope IS NULL``；API 展示 ``team``（POST body 仍可用 ``scope=team``）
    - BYOK：``scope=user`` + ``scope_id``；``tenant_id`` 为空

    与 ``BudgetScope`` 语义独立，禁止合并字面量。
    """

    SYSTEM = "system"
    TEAM = "team"  # 租户（团队/workspace）凭据的 API 别名
    USER = "user"


class BudgetScope(str, Enum):
    """预算归属作用域（写入维度）。

    描述 ``gateway_budgets.target_kind`` 列：一条预算记录绑定在哪一层。
    与 ``CredentialScope`` 同形（``system|tenant|user``）但 BudgetScope 多 ``key``（单个虚拟 Key）；
    两者各自独立演进，禁止合并字面量。

    与 ``domains.gateway.domain.usage_read_model.UsageAggregation`` **正交**：
    BudgetScope 是"预算条目属于谁"（写入字段），UsageAggregation 是
    "查询用量时按哪一列切片"（HTTP 查询参数）。``BudgetScope.tenant`` 与
    ``UsageAggregation.workspace`` 保持不同字面量，避免 URL/JSON 语义模糊。
    """

    SYSTEM = "system"
    TENANT = "tenant"
    KEY = "key"  # 单个虚拟 Key
    USER = "user"


class DownstreamPricingScope(str, Enum):
    """``downstream_model_pricing.scope`` 字面量。"""

    GLOBAL = "global"
    TENANT = "tenant"
    ENTITLEMENT_PLAN = "entitlement_plan"


def normalize_downstream_pricing_scope(scope: str) -> str:
    """API/历史 ``team`` 写入统一为 ``tenant``。"""
    if scope == "team":
        return DownstreamPricingScope.TENANT.value
    return scope


class BudgetPeriod(str, Enum):
    """预算周期"""

    DAILY = "daily"
    MONTHLY = "monthly"
    TOTAL = "total"  # 累计（不重置）


class GatewayCapability(str, Enum):
    """Gateway 调用能力（与 OpenAI 兼容入口对应）"""

    CHAT = "chat"
    EMBEDDING = "embedding"
    IMAGE = "image"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    AUDIO_SPEECH = "audio_speech"
    RERANK = "rerank"
    VIDEO_GENERATION = "video_generation"
    MODERATION = "moderation"


def allowed_capabilities_from_storage(
    raw: list[str] | tuple[str, ...] | None,
) -> tuple[GatewayCapability, ...]:
    """将存储层/请求中的能力字符串列规范为 ``GatewayCapability`` 元组。

    空值与纯空白项跳过；无法解析为枚举的值抛出 ``ValueError``。
    """
    if not raw:
        return ()
    out: list[GatewayCapability] = []
    for item in raw:
        key = str(item).strip()
        if not key:
            continue
        try:
            out.append(GatewayCapability(key))
        except ValueError as exc:
            raise ValueError(f"invalid gateway capability: {key!r}") from exc
    return tuple(out)


class RoutingStrategy(str, Enum):
    """路由策略（对齐 LiteLLM Router）"""

    SIMPLE_SHUFFLE = "simple-shuffle"
    LEAST_BUSY = "least-busy"
    LATENCY_BASED = "latency-based-routing"
    USAGE_BASED = "usage-based-routing-v2"
    COST_BASED = "cost-based-routing"


class FallbackKind(str, Enum):
    """Fallback 类型"""

    GENERAL = "general"
    CONTENT_POLICY = "content_policy"
    CONTEXT_WINDOW = "context_window"


class RequestStatus(str, Enum):
    """调用状态"""

    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BUDGET_EXCEEDED = "budget_exceeded"
    GUARDRAIL_BLOCKED = "guardrail_blocked"


class AlertMetric(str, Enum):
    """告警指标"""

    ERROR_RATE = "error_rate"
    BUDGET_USAGE = "budget_usage"
    LATENCY_P95 = "latency_p95"
    REQUEST_RATE = "request_rate"


class AlertChannel(str, Enum):
    """告警通知渠道"""

    WEBHOOK = "webhook"
    INAPP = "inapp"
    EMAIL = "email"


# 入站鉴权路径：虚拟 Key（sk-gw-*）或 Identity 平台 Key（sk-* + gateway:proxy）
GatewayInboundVia = Literal["vkey", "apikey"]

# 模型列表 / 选择器展示的 entitlement 状态（与前端 EntitlementStatus 对齐）
EntitlementListStatus = Literal["active", "exhausted", "expired", "none", "resetting"]

# 连通性探针在列表 API 中的取值；未测过用 JSON null（Python None）
ModelConnectivityStatus = Literal["success", "failed"]

VirtualKeyBatchRevokeReason = Literal["not_found", "permission_denied", "system_key"]


# =============================================================================
# 值对象与 DTO
# =============================================================================


@dataclass(frozen=True)
class TeamContext:
    """团队上下文（请求级，注入 PermissionContext）"""

    team_id: uuid.UUID
    team_role: TeamRole
    team_kind: TeamKind = TeamKind.PERSONAL


@dataclass(frozen=True)
class VirtualKeyPrincipal:
    """虚拟 Key 鉴权后的主体信息"""

    vkey_id: uuid.UUID
    vkey_name: str
    team_id: uuid.UUID
    user_id: uuid.UUID | None  # 创建者
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[GatewayCapability, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool
    is_system: bool


@dataclass(frozen=True)
class ApiKeyGatewayGrantPrincipal:
    """平台 API Key 的 Gateway grant 主体信息。"""

    grant_id: uuid.UUID
    api_key_id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[GatewayCapability, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool


@dataclass
class RouteConfig:
    """路由配置（对齐 LiteLLM Router 的 model_list 配置）"""

    virtual_model: str
    primary_models: list[str]
    fallbacks_general: list[str] = field(default_factory=list)
    fallbacks_content_policy: list[str] = field(default_factory=list)
    fallbacks_context_window: list[str] = field(default_factory=list)
    strategy: RoutingStrategy = RoutingStrategy.SIMPLE_SHUFFLE
    retry_policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """单次调用的用量记录（写日志前的中间表示）"""

    capability: GatewayCapability
    real_model: str
    provider: str
    status: RequestStatus
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    ttfb_ms: int | None = None
    error_code: str | None = None
    cache_hit: bool = False
    fallback_chain: list[str] = field(default_factory=list)


@dataclass
class DashboardSummary:
    """仪表盘汇总"""

    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    success_count: int
    failure_count: int
    avg_latency_ms: float
    p95_latency_ms: float


@dataclass
class TimeSeriesPoint:
    """时序点"""

    bucket: datetime
    requests: int
    tokens: int
    cost_usd: Decimal
    errors: int


# app.toml / 环境变量同步写入的系统凭据固定名与 extra 标记（与 GatewayModel.tags.managed_by 同源语义）。
CONFIG_MANAGED_CREDENTIAL_NAME = "app-config-default"
CONFIG_MANAGED_BY = "config"
GATEWAY_MODEL_MANAGED_BY_TAG = "managed_by"
# 凭据停用级联禁用模型时写入 tags；再次启用凭据时仅恢复带此标记的模型。
CREDENTIAL_CASCADE_DISABLED_TAG = "disabled_by_credential"


def credential_api_scope(
    *,
    scope: str | None,
    tenant_id: uuid.UUID | None,
) -> str:
    """将 ORM/读模型坐标映射为稳定的 API / metadata scope 字面量。"""
    if scope == CredentialScope.SYSTEM.value:
        return CredentialScope.SYSTEM.value
    if scope == CredentialScope.USER.value:
        return CredentialScope.USER.value
    if scope == CredentialScope.TEAM.value or tenant_id is not None:
        return CredentialScope.TEAM.value
    if scope is None and tenant_id is None:
        return CredentialScope.SYSTEM.value
    return CredentialScope.USER.value


def is_config_managed_system_credential(
    *,
    scope: str | None,
    name: str,
    extra: dict[str, Any] | None,
    tenant_id: uuid.UUID | None = None,
) -> bool:
    """是否为配置同步托管的 system 凭据（不可重命名，同步按 provider 幂等更新）。"""
    if credential_api_scope(scope=scope, tenant_id=tenant_id) != CredentialScope.SYSTEM.value:
        return False
    if (extra or {}).get("managed_by") == CONFIG_MANAGED_BY:
        return True
    return name == CONFIG_MANAGED_CREDENTIAL_NAME


def is_config_managed_system_gateway_model(*, tags: dict[str, Any] | None) -> bool:
    """是否为配置同步托管的系统注册模型（不可删除/不可改别名）。"""
    return (tags or {}).get(GATEWAY_MODEL_MANAGED_BY_TAG) == CONFIG_MANAGED_BY


# 用户 BYOK：``/my-credentials`` 所支持的提供商标识（与路由/LiteLLM 对齐，不含 custom）。
USER_GATEWAY_CREDENTIAL_PROVIDERS: frozenset[str] = frozenset(
    {"openai", "anthropic", "dashscope", "zhipuai", "deepseek", "volcengine"}
)

# 团队/系统凭据创建支持的 provider 标识 ——
# 与前端 ``provider-schemas.ts`` 的 schema 表保持一致，并涵盖 USER 集合作为子集。
MANAGED_GATEWAY_CREDENTIAL_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "anthropic",
        "azure",
        "bedrock",
        "gemini",
        "vertex_ai",
        "dashscope",
        "deepseek",
        "volcengine",
        "zhipuai",
        "cohere",
        "mistral",
        "fireworks",
        "together_ai",
    }
)

# personal team gateway_models 允许的 model_types（与选择器 type 对齐）。
PERSONAL_MODEL_TYPES: frozenset[str] = frozenset({"text", "image", "image_gen", "video"})

# personal team 模型注册允许的 provider（含 custom：自定义 base + model_id）。
PERSONAL_MODEL_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "deepseek",
        "dashscope",
        "anthropic",
        "zhipuai",
        "volcengine",
        "custom",
    }
)


__all__ = [
    "CONFIG_MANAGED_BY",
    "CONFIG_MANAGED_CREDENTIAL_NAME",
    "CREDENTIAL_CASCADE_DISABLED_TAG",
    "GATEWAY_MODEL_MANAGED_BY_TAG",
    "MANAGED_GATEWAY_CREDENTIAL_PROVIDERS",
    "PERSONAL_MODEL_PROVIDERS",
    "PERSONAL_MODEL_TYPES",
    "USER_GATEWAY_CREDENTIAL_PROVIDERS",
    "AlertChannel",
    "AlertMetric",
    "ApiKeyGatewayGrantPrincipal",
    "BudgetPeriod",
    "BudgetScope",
    "CredentialScope",
    "DashboardSummary",
    "DownstreamPricingScope",
    "EntitlementListStatus",
    "FallbackKind",
    "GatewayCapability",
    "GatewayInboundVia",
    "ManagementTeamContext",
    "ModelConnectivityStatus",
    "RequestStatus",
    "RouteConfig",
    "RoutingStrategy",
    "TeamContext",
    "TeamKind",
    "TeamRole",
    "TimeSeriesPoint",
    "UsageRecord",
    "VirtualKeyBatchRevokeReason",
    "VirtualKeyPrincipal",
    "allowed_capabilities_from_storage",
    "credential_api_scope",
    "is_config_managed_system_credential",
    "is_config_managed_system_gateway_model",
    "normalize_downstream_pricing_scope",
]
