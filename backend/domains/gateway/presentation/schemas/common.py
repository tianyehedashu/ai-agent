"""Gateway Pydantic Schemas"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.gateway.domain.margin_read_model import MarginGroupBy
from domains.gateway.domain.types import RoutingStrategy, VirtualKeyBatchRevokeReason
from domains.gateway.domain.usage_read_model import UsageStatisticsGroupBy
from libs.api.pagination import PaginatedListResponse

# =============================================================================
# Gateway features（运行时能力开关，与部署 env 对齐）
# =============================================================================


class GatewayFeaturesResponse(BaseModel):
    """控制台与创建 Key 表单读取的全局能力开关。"""

    pii_guardrail_globally_enabled: bool


# =============================================================================
# Virtual Key
# =============================================================================


class VirtualKeyCreate(BaseModel):
    name: str
    description: str | None = None
    allowed_models: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    store_full_messages: bool = False
    guardrail_enabled: bool = False
    expires_in_days: int | None = None


class VirtualKeyResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None = None
    masked_key: str
    allowed_models: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    store_full_messages: bool = False
    guardrail_enabled: bool = False
    is_system: bool = False
    is_active: bool = True
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    usage_count: int = 0
    created_at: datetime


class VirtualKeyCreateResponse(VirtualKeyResponse):
    plain_key: str = Field(description="完整的 sk-gw-... Key（仅创建时返回一次）")


class VirtualKeyRevealResponse(BaseModel):
    """显式 reveal 接口返回的完整明文（与 ``VirtualKeyCreateResponse.plain_key`` 同语义）。"""

    plain_key: str = Field(description="完整的 sk-gw-... Key 明文")


class VirtualKeyBatchRevokeRequest(BaseModel):
    key_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class VirtualKeyBatchRevokeFailureItem(BaseModel):
    key_id: uuid.UUID
    reason: VirtualKeyBatchRevokeReason


class VirtualKeyBatchRevokeResponse(BaseModel):
    revoked: list[uuid.UUID] = Field(default_factory=list)
    failed: list[VirtualKeyBatchRevokeFailureItem] = Field(default_factory=list)


# =============================================================================
# Credential
# =============================================================================


class UserCredentialCreate(BaseModel):
    """POST /my-credentials：用户私有凭据（无 scope 字段，避免与团队管理 DTO 混淆）"""

    provider: str
    name: str
    api_key: str
    api_base: str | None = None
    profile_id: str | None = Field(
        default=None,
        description="上游方案 ID（如 volcengine.coding_plan）；省略则使用 provider.default",
    )
    extra: dict[str, Any] | None = None


class ManagedCredentialCreate(BaseModel):
    """POST /api/v1/gateway/credentials：租户或系统级凭据。

    ``scope=team`` 表示写入当前 X-Team-Id 租户（落库 ``tenant_id`` + ``scope NULL``）；
    ``scope=system`` 仅平台管理员，写入 ``system_provider_credentials``。
    """

    provider: str
    name: str
    api_key: str
    api_base: str | None = None
    profile_id: str | None = Field(
        default=None,
        description="上游方案 ID（如 volcengine.coding_plan）；省略则使用 provider.default",
    )
    extra: dict[str, Any] | None = None
    scope: Literal["team", "system"] = "team"


class CredentialUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    profile_id: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool | None = None


class CredentialResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    scope: str | None = None
    scope_id: uuid.UUID | None = None
    provider: str
    name: str
    api_base: str | None = None
    profile_id: str | None = Field(
        default=None,
        description="上游方案 ID；NULL 表示 provider.default",
    )
    profile_label: str | None = Field(
        default=None,
        description="方案展示名（来自 SSOT 注册表）",
    )
    effective_api_base_openai: str | None = Field(
        default=None,
        description="OpenAI-compat 协议下的有效 api_base（解析后）",
    )
    effective_api_base_anthropic: str | None = Field(
        default=None,
        description="Anthropic-native 协议下的有效 api_base（若 profile 支持）",
    )
    extra: dict[str, Any] | None = None
    is_active: bool = True
    is_config_managed: bool = Field(
        default=False,
        description="app.toml/环境变量同步托管的 system 凭据（不可重命名；删除后同步可能恢复）",
    )
    visibility: Literal["public", "restricted"] | None = Field(
        default=None,
        description="系统凭据可见性；团队/BYOK 凭据无此字段",
    )
    created_at: datetime
    api_key_masked: str = Field(
        description="解密后仅用于展示的掩码，不包含完整密钥",
    )

    model_config = ConfigDict(from_attributes=False)


class CredentialSummaryResponse(BaseModel):
    """凭据摘要：供团队 member 解析模型上的 credential_id，不含密钥与 api_base。"""

    id: uuid.UUID
    provider: str
    name: str
    scope: str | None = None
    is_active: bool = True
    is_config_managed: bool = Field(
        default=False,
        description="app.toml/环境变量同步托管的 system 凭据",
    )

    model_config = ConfigDict(from_attributes=False)


class ManagedTeamCredentialListResponse(PaginatedListResponse[CredentialResponse]):
    """跨可写团队聚合的团队 scope 凭据列表。"""

    queried_team_count: int = Field(
        ge=0,
        description="search 过滤后参与聚合的可写团队数量",
    )
    queried_personal_team_count: int = Field(
        ge=0,
        description="参与聚合的注册用户 personal team 数量",
    )
    queried_shared_team_count: int = Field(
        ge=0,
        description="参与聚合的协作团队数量",
    )


# =============================================================================
# Gateway Model
# =============================================================================


class SystemCredentialSummary(BaseModel):
    """系统模型绑定的平台凭据摘要（仅 PlatformAdmin 列表返回）。"""

    id: uuid.UUID
    provider: str
    name: str
    visibility: Literal["public", "restricted"] = "public"


class SystemVisibilityPatch(BaseModel):
    visibility: Literal["public", "restricted"]


class SystemModelVisibilityPatch(BaseModel):
    visibility: Literal["inherit", "public", "restricted"]


class SystemGatewayGrantCreate(BaseModel):
    subject_kind: Literal["credential", "model"]
    subject_id: uuid.UUID
    target_kind: Literal["team", "user"]
    target_id: uuid.UUID
    note: str | None = None


class SystemGatewayGrantUpdate(BaseModel):
    enabled: bool | None = None
    note: str | None = None


class SystemGatewayGrantResponse(BaseModel):
    id: uuid.UUID
    subject_kind: Literal["credential", "model"]
    subject_id: uuid.UUID
    target_kind: Literal["team", "user"]
    target_id: uuid.UUID
    enabled: bool
    note: str | None = None
    granted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemVisibilityTargetSnapshot(BaseModel):
    """某 team/user 当前命中的 grants 与可见系统模型名。"""

    target_kind: Literal["team", "user"]
    target_id: uuid.UUID
    grants: list[SystemGatewayGrantResponse] = Field(default_factory=list)
    visible_model_names: list[str] = Field(default_factory=list)


class GatewayModelCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="虚拟模型别名；同一团队内 (name) 唯一",
    )
    capability: str = Field(
        ...,
        description=(
            "OpenAI 兼容主调用面（chat / embedding / image / …），决定该别名默认绑定的 HTTP 入口；"
            "多模态特性请写在 tags 中"
        ),
    )
    real_model: str
    credential_id: uuid.UUID
    provider: str
    weight: int = 1
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    tags: dict[str, Any] | None = None
    upstream_call_shape: str | None = Field(
        default=None,
        description="出站 LiteLLM 调用形：openai_compat / anthropic_native；NULL=跟随凭据 profile",
    )
    enabled: bool = True


class MultiCredentialGatewayModelCreate(BaseModel):
    """同一 ``(provider, real_model)`` 在多个凭据上一键注册并自动生成 ``GatewayRoute``。

    后端会为每个 ``credential_id`` 创建独立 ``GatewayModel``，别名形如 ``<name>--<cred短哈希>``；
    同时建立 ``GatewayRoute(virtual_model=name, primary_models=[...])``。客户端调用 ``model=name``
    即可由 Router 在所有 deployment 间按 ``strategy`` 调度。"""

    name: str = Field(
        ..., min_length=1, max_length=200, description="对外虚拟模型名；将创建同名 GatewayRoute"
    )
    capability: str
    real_model: str
    provider: str
    credential_ids: list[uuid.UUID] = Field(..., min_length=1)
    strategy: RoutingStrategy = Field(
        default=RoutingStrategy.SIMPLE_SHUFFLE,
        description="LiteLLM Router 调度策略（见 RoutingStrategy 枚举）",
    )
    weight: int = 1
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    tags: dict[str, Any] | None = None
    upstream_call_shape: str | None = None
    enabled: bool = True


class MultiCredentialGatewayModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: uuid.UUID
    virtual_model: str
    strategy: str
    primary_models: list[str]
    created_model_ids: list[uuid.UUID]


class GatewayModelUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="虚拟模型别名；同一团队内 (team_id, name) 唯一",
    )
    real_model: str | None = None
    credential_id: uuid.UUID | None = None
    weight: int | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    enabled: bool | None = None
    tags: dict[str, Any] | None = None
    resync_capabilities: bool = Field(
        default=False,
        description="为 true 时从 LiteLLM model_cost 重算能力 tags（不持久化该字段）",
    )
    upstream_call_shape: str | None = Field(
        default=None,
        description="出站 LiteLLM 调用形：openai_compat / anthropic_native",
    )


class ModelSelectorCapabilities(BaseModel):
    """与 ``ModelCapabilitySnapshot`` / 选择器扁平字段对齐。"""

    supports_vision: bool = False
    supports_tools: bool = True
    supports_reasoning: bool = False
    thinking_param: str = "none"
    temperature_policy: str = "client"
    temperature_default: float = 0.7
    supports_json_mode: bool = True
    supports_image_gen: bool = False
    supports_txt2img: bool = True
    supports_img2img: bool = False
    supports_video_gen: bool = False
    supports_image_to_video: bool = False
    max_reference_images: int = 0


class GatewayModelResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    registry_kind: Literal["team", "system"] = Field(
        default="team",
        description="注册表归属：team=租户 gateway_models；system=平台 system_gateway_models",
    )
    name: str
    capability: str = Field(
        description="主调用面：与 OpenAI 兼容路由入口一致，不等同于 tags 中的多特性组合",
    )
    real_model: str
    credential_id: uuid.UUID
    provider: str
    weight: int = 1
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    enabled: bool = True
    tags: dict[str, Any] | None = None
    upstream_call_shape: str | None = Field(
        default=None,
        description="出站 LiteLLM 调用形：openai_compat / anthropic_native",
    )
    model_types: list[str] = Field(
        default_factory=list,
        description="选择器用特性类型（由 tags + capability 推导，如 text / image / image_gen / video）",
    )
    selector_capabilities: dict[str, Any] = Field(
        default_factory=dict,
        description="与 ModelCapabilitySnapshot 对齐的扁平布尔/数值，供前端展示特性芯片",
    )
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    last_test_reason: str | None = None
    visibility: str | None = Field(
        default=None,
        description="系统模型可见性：inherit/public/restricted；团队行无此字段",
    )
    system_credential: SystemCredentialSummary | None = Field(
        default=None,
        description="平台管理员视角：系统模型绑定的厂商凭据摘要",
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _derive_model_types_and_capabilities(self) -> Self:
        from domains.gateway.application.config_catalog_sync import (
            model_types_for_gateway_registration,
            selector_capabilities_from_tags,
        )

        tags = self.tags or {}
        return self.model_copy(
            update={
                "model_types": model_types_for_gateway_registration(tags, self.capability),
                "selector_capabilities": selector_capabilities_from_tags(
                    tags, provider=self.provider, real_model=self.real_model
                ),
            }
        )


class ModelConnectivitySummary(BaseModel):
    total: int = 0
    available: int = 0
    unavailable: int = 0
    success: int = 0
    failed: int = 0
    unknown: int = 0


class GatewayModelListResponse(PaginatedListResponse[GatewayModelResponse]):
    connectivity_summary: ModelConnectivitySummary


class GatewayModelIdsResponse(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list)
    truncated: bool = False


class PaginatedSelectorModels(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    has_next: bool
    has_prev: bool


class AvailableModelsListResponse(BaseModel):
    system_models: PaginatedSelectorModels
    user_models: PaginatedSelectorModels
    default_for_text: dict[str, str] | None = None
    default_for_vision: dict[str, str] | None = None
    default_for_image_gen: dict[str, str] | None = None
    connectivity_summary: ModelConnectivitySummary | None = None


class GatewayModelRouteUsageSlice(BaseModel):
    """单一路由名（与注册 ``GatewayModel.name`` / 请求 ``model`` 对齐）在一时间窗内的用量切片。"""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")


class GatewayModelRouteUsageItem(BaseModel):
    route_name: str
    workspace: GatewayModelRouteUsageSlice
    user: GatewayModelRouteUsageSlice


class GatewayModelUsageSummaryResponse(BaseModel):
    start: datetime
    end: datetime
    items: list[GatewayModelRouteUsageItem]


class PlatformCredentialStatItem(BaseModel):
    """平台管理员：凭据维度全局调用统计（不含密钥）。"""

    credential_id: uuid.UUID
    provider: str
    name: str
    scope: str
    scope_id: uuid.UUID | None = None
    is_active: bool = False
    gateway_model_count: int = 0
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    success_count: int = 0
    failure_count: int = 0


class PersonalModelCreate(BaseModel):
    """POST /my-credentials 同级的个人模型注册（按 model_type 拆分为多行 gateway_models）。"""

    display_name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=200)
    credential_id: uuid.UUID
    model_types: list[str] = Field(default_factory=lambda: ["text"])
    tags: dict[str, Any] | None = None


class PersonalModelUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    model_id: str | None = Field(None, min_length=1, max_length=200)
    credential_id: uuid.UUID | None = None
    is_active: bool | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def _normalize_enabled(self) -> Self:
        if self.enabled is not None and self.is_active is None:
            return self.model_copy(update={"is_active": self.enabled})
        return self


class PersonalModelResponse(BaseModel):
    """与 ``gateway_model_to_personal_list_item`` 字段对齐的个人模型列表项。"""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None
    display_name: str
    provider: str
    model_id: str
    api_key_masked: str | None = None
    has_api_key: bool = True
    api_base: str | None = None
    credential_id: uuid.UUID
    model_types: list[str] = Field(default_factory=list)
    config: dict[str, Any] | None = None
    is_active: bool
    is_system: bool = False
    capability: str
    name: str
    selector_capabilities: dict[str, Any] = Field(default_factory=dict)
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    last_test_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_gateway_model(cls, row: Any) -> Self:
        from domains.gateway.application.personal_models import gateway_model_to_personal_list_item

        raw = gateway_model_to_personal_list_item(row)

        def _dt(key: str) -> datetime | None:
            val = raw.get(key)
            if val is None:
                return None
            return datetime.fromisoformat(str(val))

        def _uuid(key: str) -> uuid.UUID | None:
            val = raw.get(key)
            return uuid.UUID(str(val)) if val else None

        return cls(
            id=uuid.UUID(str(raw["id"])),
            user_id=_uuid("user_id"),
            anonymous_user_id=raw.get("anonymous_user_id"),
            display_name=str(raw["display_name"]),
            provider=str(raw["provider"]),
            model_id=str(raw["model_id"]),
            api_key_masked=raw.get("api_key_masked"),
            has_api_key=bool(raw.get("has_api_key", True)),
            api_base=raw.get("api_base"),
            credential_id=uuid.UUID(str(raw["credential_id"])),
            model_types=list(raw.get("model_types") or []),
            config=raw.get("config"),
            is_active=bool(raw["is_active"]),
            is_system=bool(raw.get("is_system", False)),
            capability=str(raw["capability"]),
            name=str(raw["name"]),
            selector_capabilities=dict(raw.get("selector_capabilities") or {}),
            last_test_status=raw.get("last_test_status"),
            last_tested_at=_dt("last_tested_at"),
            last_test_reason=raw.get("last_test_reason"),
            created_at=_dt("created_at"),
            updated_at=_dt("updated_at"),
        )


class PersonalModelListResponse(PaginatedListResponse[PersonalModelResponse]):
    connectivity_summary: ModelConnectivitySummary


class GatewayModelTestResponse(BaseModel):
    """模型连通性测试响应。

    无论成功/失败均返回 200 + ``success`` 字段，便于前端单层 if 处理；同时
    ``status`` / ``tested_at`` 与 ORM 落库字段保持同名，前端拿到响应即可同步
    或直接 invalidate 列表查询。
    """

    success: bool
    message: str
    model: str
    status: str
    tested_at: datetime
    reason: str | None = None
    response_preview: str | None = None


class GatewayModelBatchDeleteRequest(BaseModel):
    model_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)


class GatewayModelBatchDeleteFailureItem(BaseModel):
    id: uuid.UUID
    code: str
    message: str


class GatewayModelBatchDeleteResponse(BaseModel):
    succeeded: list[uuid.UUID]
    failed: list[GatewayModelBatchDeleteFailureItem]
    grants_removed: int = 0
    budgets_removed: int = 0


class GatewayModelBatchResyncCapabilitiesRequest(BaseModel):
    model_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)


class GatewayModelBatchResyncCapabilitiesResponse(BaseModel):
    succeeded: list[uuid.UUID]
    failed: list[GatewayModelBatchDeleteFailureItem]


class GatewayModelPresetResponse(BaseModel):
    id: str
    name: str
    provider: str
    real_model: str
    capability: str = Field(
        description="主调用面（与 OpenAI 兼容入口一致）；多模态/生图等见 model_types 与 selector_capabilities",
    )
    context_window: int
    input_price: float
    output_price: float
    supports_vision: bool
    supports_tools: bool
    supports_reasoning: bool
    recommended_for: list[str] = Field(default_factory=list)
    description: str = ""
    model_types: list[str] = Field(
        default_factory=list,
        description="选择器用特性类型（由目录 tags + capability 推导）",
    )
    selector_capabilities: dict[str, Any] = Field(
        default_factory=dict,
        description="与注册模型 tags 对齐的扁平特性，便于与列表接口展示一致",
    )


# =============================================================================
# Routes
# =============================================================================


class RouteCreate(BaseModel):
    virtual_model: str
    primary_models: list[str]
    fallbacks_general: list[str] = Field(default_factory=list)
    fallbacks_content_policy: list[str] = Field(default_factory=list)
    fallbacks_context_window: list[str] = Field(default_factory=list)
    strategy: RoutingStrategy = RoutingStrategy.SIMPLE_SHUFFLE
    retry_policy: dict[str, Any] | None = None


class RouteUpdate(BaseModel):
    primary_models: list[str] | None = None
    fallbacks_general: list[str] | None = None
    fallbacks_content_policy: list[str] | None = None
    fallbacks_context_window: list[str] | None = None
    strategy: RoutingStrategy | None = None
    retry_policy: dict[str, Any] | None = None
    enabled: bool | None = None


class RouteResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    source: Literal["team", "system"] = "team"
    virtual_model: str
    primary_models: list[str]
    fallbacks_general: list[str]
    fallbacks_content_policy: list[str]
    fallbacks_context_window: list[str]
    strategy: str
    retry_policy: dict[str, Any] | None = None
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Budget
# =============================================================================


class BudgetUpsert(BaseModel):
    target_kind: str = Field(pattern="^(system|tenant|key|user)$")
    target_id: uuid.UUID | None = None
    period: str = Field(pattern="^(daily|monthly|total)$")
    model_name: str | None = Field(
        default=None,
        max_length=200,
        description="非空时仅对该请求 model 字符串计量；省略为全模型汇总",
    )
    limit_usd: Decimal | None = None
    soft_limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None


class BudgetResponse(BaseModel):
    id: uuid.UUID
    target_kind: str
    target_id: uuid.UUID | None = None
    period: str
    model_name: str | None = None
    limit_usd: Decimal | None = None
    soft_limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    current_usd: Decimal = Decimal("0")
    current_tokens: int = 0
    current_requests: int = 0
    reset_at: datetime | None = None
    budget_reset_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Logs
# =============================================================================


class RequestLogResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    team_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    vkey_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    credential_name_snapshot: str | None = None
    deployment_gateway_model_id: uuid.UUID | None = None
    deployment_model_name: str | None = None
    capability: str
    route_name: str | None = None
    real_model: str | None = None
    provider: str | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    revenue_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    ttfb_ms: int | None = None
    cache_hit: bool = False
    fallback_chain: list[str] = Field(default_factory=list)
    request_id: str | None = None
    prompt_hash: str | None = None
    user_email_snapshot: str | None = None
    vkey_name_snapshot: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RequestLogDetailResponse(RequestLogResponse):
    """单条日志详情：含脱敏 prompt/响应摘要等大字段（列表接口不返回）。"""

    team_snapshot: dict[str, Any] | None = None
    route_snapshot: dict[str, Any] | None = None
    prompt_redacted: dict[str, Any] | None = None
    response_summary: dict[str, Any] | None = None
    metadata_extra: dict[str, Any] | None = None
    pricing_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class RequestLogListResponse(BaseModel):
    items: list[RequestLogResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Dashboard
# =============================================================================


class DashboardClientTypeBreakdown(BaseModel):
    client_type: str
    requests: int
    cost_usd: Decimal


class DashboardSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    success_count: int
    failure_count: int
    avg_latency_ms: float
    success_rate: float
    by_client_type: list[DashboardClientTypeBreakdown] = Field(default_factory=list)


class TimeSeriesPointResponse(BaseModel):
    bucket: datetime
    requests: int
    tokens: int
    cost_usd: Decimal
    errors: int


class UsageStatisticsMetricResponse(BaseModel):
    requests: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    cost_usd: Decimal
    avg_latency_ms: float
    cache_hit_count: int
    success_rate: float
    cache_hit_rate: float


class UsageStatisticsItemResponse(UsageStatisticsMetricResponse):
    group_key: str
    label: str


class UsageStatisticsResponse(BaseModel):
    start: datetime
    end: datetime
    group_by: UsageStatisticsGroupBy
    totals: UsageStatisticsMetricResponse
    items: list[UsageStatisticsItemResponse] = Field(default_factory=list)


# =============================================================================
# Alert
# =============================================================================


class AlertRuleCreate(BaseModel):
    name: str
    description: str | None = None
    metric: str = Field(pattern="^(error_rate|budget_usage|latency_p95|request_rate)$")
    threshold: float
    window_minutes: int = 5
    channels: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    threshold: float | None = None
    window_minutes: int | None = None
    channels: dict[str, Any] | None = None
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    metric: str
    threshold: float
    window_minutes: int
    channels: dict[str, Any]
    enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertEventResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    metric_value: float
    threshold: float
    severity: str
    payload: dict[str, Any] | None = None
    notified: bool
    acknowledged: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Plan (Provider / Entitlement) — 上下游对称
# =============================================================================


PlanResetStrategy = Literal[
    "rolling",
    "calendar_daily_utc",
    "calendar_monthly_utc",
    "plan_anniversary",
]


class PlanQuotaUpsert(BaseModel):
    """通用 plan quota 输入；上下游共用，非空字段才设置。"""

    label: str = Field(..., min_length=1, max_length=40)
    window_seconds: int = Field(..., ge=0, description="0 表示整套餐有效期作为一个累计桶")
    reset_strategy: PlanResetStrategy = Field(
        default="rolling",
        description=(
            "重置策略：rolling=滚动窗口；calendar_daily_utc=每日 UTC 重置；"
            "calendar_monthly_utc=自然月重置；plan_anniversary=按 valid_from 切片"
        ),
    )
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None


class EntitlementPlanQuotaUpsert(PlanQuotaUpsert):
    unit_price_usd_per_token: Decimal | None = None
    unit_price_usd_per_request: Decimal | None = None


class ProviderPlanCreate(BaseModel):
    real_model: str | None = None
    label: str = Field(..., min_length=1, max_length=100)
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True
    auto_renew: bool = False
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[PlanQuotaUpsert] = Field(default_factory=list)


class ProviderPlanUpdate(BaseModel):
    real_model: str | None = None
    label: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None
    auto_renew: bool | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[PlanQuotaUpsert] | None = None


class PlanQuotaResponse(BaseModel):
    id: uuid.UUID
    label: str
    window_seconds: int
    reset_strategy: PlanResetStrategy = "rolling"
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EntitlementPlanQuotaResponse(PlanQuotaResponse):
    unit_price_usd_per_token: Decimal | None = None
    unit_price_usd_per_request: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class ProviderPlanResponse(BaseModel):
    id: uuid.UUID
    credential_id: uuid.UUID
    real_model: str | None = None
    label: str
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    auto_renew: bool
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[PlanQuotaResponse] = Field(default_factory=list)


class EntitlementPlanCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    valid_from: datetime
    valid_until: datetime
    included_models: list[str] = Field(default_factory=list)
    included_capabilities: list[str] = Field(default_factory=list)
    is_active: bool = True
    auto_renew: bool = False
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[EntitlementPlanQuotaUpsert] = Field(default_factory=list)


class EntitlementPlanUpdate(BaseModel):
    label: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    included_models: list[str] | None = None
    included_capabilities: list[str] | None = None
    is_active: bool | None = None
    auto_renew: bool | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[EntitlementPlanQuotaUpsert] | None = None


class EntitlementPlanResponse(BaseModel):
    id: uuid.UUID
    scope: str
    scope_id: uuid.UUID
    label: str
    valid_from: datetime
    valid_until: datetime
    included_models: list[str] = Field(default_factory=list)
    included_capabilities: list[str] = Field(default_factory=list)
    is_active: bool
    auto_renew: bool
    notes: str | None = None
    extra: dict[str, Any] | None = None
    quotas: list[EntitlementPlanQuotaResponse] = Field(default_factory=list)


class EntitlementUsageResponse(BaseModel):
    plan_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    charged_usd: Decimal


class ProviderPlanCostResponse(BaseModel):
    plan_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class MarginGroupItemResponse(BaseModel):
    group_key: str
    label: str
    revenue_usd: Decimal
    cost_usd: Decimal
    margin_usd: Decimal
    margin_ratio: float


class MarginSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_revenue_usd: Decimal
    total_cost_usd: Decimal
    total_margin_usd: Decimal
    group_by: MarginGroupBy = "credential"
    group_column_label: str = "凭据"
    items: list[MarginGroupItemResponse] = Field(default_factory=list)


__all__ = [
    "AlertEventResponse",
    "AlertRuleCreate",
    "AlertRuleResponse",
    "AlertRuleUpdate",
    "BudgetResponse",
    "BudgetUpsert",
    "CredentialResponse",
    "ManagedTeamCredentialListResponse",
    "CredentialUpdate",
    "DashboardSummaryResponse",
    "EntitlementPlanCreate",
    "EntitlementPlanQuotaResponse",
    "EntitlementPlanQuotaUpsert",
    "EntitlementPlanResponse",
    "EntitlementPlanUpdate",
    "EntitlementUsageResponse",
    "GatewayModelBatchDeleteFailureItem",
    "GatewayModelBatchDeleteRequest",
    "GatewayModelBatchDeleteResponse",
    "GatewayModelBatchResyncCapabilitiesRequest",
    "GatewayModelBatchResyncCapabilitiesResponse",
    "GatewayModelIdsResponse",
    "GatewayModelListResponse",
    "GatewayModelPresetResponse",
    "GatewayModelResponse",
    "GatewayModelRouteUsageItem",
    "GatewayModelRouteUsageSlice",
    "GatewayModelTestResponse",
    "GatewayModelUpdate",
    "GatewayModelUsageSummaryResponse",
    "MarginGroupItemResponse",
    "MarginSummaryResponse",
    "ModelConnectivitySummary",
    "PaginatedSelectorModels",
    "PersonalModelCreate",
    "PersonalModelListResponse",
    "PersonalModelResponse",
    "PersonalModelUpdate",
    "PlanQuotaResponse",
    "PlanQuotaUpsert",
    "PlanResetStrategy",
    "PlatformCredentialStatItem",
    "ProviderPlanCostResponse",
    "ProviderPlanCreate",
    "ProviderPlanResponse",
    "ProviderPlanUpdate",
    "RequestLogDetailResponse",
    "RequestLogListResponse",
    "RequestLogResponse",
    "RouteCreate",
    "RouteResponse",
    "RouteUpdate",
    "SystemCredentialSummary",
    "SystemGatewayGrantCreate",
    "SystemGatewayGrantResponse",
    "SystemGatewayGrantUpdate",
    "SystemModelVisibilityPatch",
    "SystemVisibilityPatch",
    "SystemVisibilityTargetSnapshot",
    "TimeSeriesPointResponse",
    "UsageStatisticsItemResponse",
    "UsageStatisticsMetricResponse",
    "UsageStatisticsResponse",
    "UserCredentialCreate",
    "VirtualKeyCreate",
    "VirtualKeyCreateResponse",
    "VirtualKeyResponse",
]
