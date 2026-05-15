"""Gateway Pydantic Schemas"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.tenancy.presentation.schemas.teams import (
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)

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
    guardrail_enabled: bool = True
    expires_in_days: int | None = None


class VirtualKeyResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None = None
    masked_key: str
    allowed_models: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    store_full_messages: bool = False
    guardrail_enabled: bool = True
    is_system: bool = False
    is_active: bool = True
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    usage_count: int = 0
    created_at: datetime


class VirtualKeyCreateResponse(VirtualKeyResponse):
    plain_key: str = Field(description="完整的 sk-gw-... Key（仅创建时返回一次）")


# =============================================================================
# Credential
# =============================================================================


class UserCredentialCreate(BaseModel):
    """POST /my-credentials：用户私有凭据（无 scope 字段，避免与团队管理 DTO 混淆）"""

    provider: str
    name: str
    api_key: str
    api_base: str | None = None
    extra: dict[str, Any] | None = None


class ManagedCredentialCreate(BaseModel):
    """POST /api/v1/gateway/credentials：团队或系统级凭据（平台管理员可 scope=system）"""

    provider: str
    name: str
    api_key: str
    api_base: str | None = None
    extra: dict[str, Any] | None = None
    scope: Literal["team", "system"] = "team"


class CredentialUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool | None = None


class CredentialResponse(BaseModel):
    id: uuid.UUID
    scope: str
    scope_id: uuid.UUID | None = None
    provider: str
    name: str
    api_base: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool = True
    created_at: datetime
    api_key_masked: str = Field(
        description="解密后仅用于展示的掩码，不包含完整密钥",
    )

    model_config = ConfigDict(from_attributes=False)


# =============================================================================
# Gateway Model
# =============================================================================


class GatewayModelCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="虚拟模型别名；同一工作区内 (name) 唯一",
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


class GatewayModelUpdate(BaseModel):
    real_model: str | None = None
    credential_id: uuid.UUID | None = None
    weight: int | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    enabled: bool | None = None
    tags: dict[str, Any] | None = None


class GatewayModelResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID | None = None
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
                "selector_capabilities": selector_capabilities_from_tags(tags),
            }
        )


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
    strategy: str = "simple-shuffle"
    retry_policy: dict[str, Any] | None = None


class RouteUpdate(BaseModel):
    primary_models: list[str] | None = None
    fallbacks_general: list[str] | None = None
    fallbacks_content_policy: list[str] | None = None
    fallbacks_context_window: list[str] | None = None
    strategy: str | None = None
    retry_policy: dict[str, Any] | None = None
    enabled: bool | None = None


class RouteResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID | None = None
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
    scope: str = Field(pattern="^(system|team|key|user)$")
    scope_id: uuid.UUID | None = None
    period: str = Field(pattern="^(daily|monthly|total)$")
    model_name: str | None = Field(
        default=None,
        max_length=200,
        description="非空时仅对该请求 model 字符串计量；省略为全模型汇总",
    )
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None


class BudgetResponse(BaseModel):
    id: uuid.UUID
    scope: str
    scope_id: uuid.UUID | None = None
    period: str
    model_name: str | None = None
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    current_usd: Decimal = Decimal("0")
    current_tokens: int = 0
    current_requests: int = 0
    reset_at: datetime | None = None

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

    model_config = ConfigDict(from_attributes=True)


class RequestLogListResponse(BaseModel):
    items: list[RequestLogResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Dashboard
# =============================================================================


class DashboardSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    success_count: int
    failure_count: int
    avg_latency_ms: float
    success_rate: float


class TimeSeriesPointResponse(BaseModel):
    bucket: datetime
    requests: int
    tokens: int
    cost_usd: Decimal
    errors: int


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
    team_id: uuid.UUID | None = None
    metric_value: float
    threshold: float
    severity: str
    payload: dict[str, Any] | None = None
    notified: bool
    acknowledged: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "AlertEventResponse",
    "AlertRuleCreate",
    "AlertRuleResponse",
    "AlertRuleUpdate",
    "BudgetResponse",
    "BudgetUpsert",
    "CredentialResponse",
    "CredentialUpdate",
    "DashboardSummaryResponse",
    "GatewayModelCreate",
    "GatewayModelPresetResponse",
    "GatewayModelResponse",
    "GatewayModelRouteUsageItem",
    "GatewayModelRouteUsageSlice",
    "GatewayModelTestResponse",
    "GatewayModelUpdate",
    "GatewayModelUsageSummaryResponse",
    "ManagedCredentialCreate",
    "PlatformCredentialStatItem",
    "RequestLogDetailResponse",
    "RequestLogListResponse",
    "RequestLogResponse",
    "RouteCreate",
    "RouteResponse",
    "RouteUpdate",
    "TeamCreate",
    "TeamMemberAdd",
    "TeamMemberResponse",
    "TeamResponse",
    "TeamUpdate",
    "TimeSeriesPointResponse",
    "UserCredentialCreate",
    "VirtualKeyCreate",
    "VirtualKeyCreateResponse",
    "VirtualKeyResponse",
]
