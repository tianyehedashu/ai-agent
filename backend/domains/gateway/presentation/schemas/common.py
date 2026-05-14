"""Gateway Pydantic Schemas"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

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


class CredentialCreate(BaseModel):
    provider: str
    name: str
    api_key: str
    api_base: str | None = None
    extra: dict[str, Any] | None = None


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

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Gateway Model
# =============================================================================


class GatewayModelCreate(BaseModel):
    name: str
    capability: str
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
    capability: str
    real_model: str
    credential_id: uuid.UUID
    provider: str
    weight: int = 1
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    enabled: bool = True
    tags: dict[str, Any] | None = None
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    last_test_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    capability: str
    context_window: int
    input_price: float
    output_price: float
    supports_vision: bool
    supports_tools: bool
    supports_reasoning: bool
    recommended_for: list[str] = Field(default_factory=list)
    description: str = ""


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
    capability: str
    route_name: str | None = None
    real_model: str | None = None
    provider: str | None = None
    status: str
    error_code: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    cache_hit: bool = False
    fallback_chain: list[str] = Field(default_factory=list)
    request_id: str | None = None
    user_email_snapshot: str | None = None
    vkey_name_snapshot: str | None = None

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
    "CredentialCreate",
    "CredentialResponse",
    "CredentialUpdate",
    "DashboardSummaryResponse",
    "GatewayModelCreate",
    "GatewayModelPresetResponse",
    "GatewayModelResponse",
    "GatewayModelUpdate",
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
    "VirtualKeyCreate",
    "VirtualKeyCreateResponse",
    "VirtualKeyResponse",
]
