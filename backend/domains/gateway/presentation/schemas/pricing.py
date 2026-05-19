"""定价目录 API Schema。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MoneyDisplaySchema(BaseModel):
    model_config = ConfigDict(strict=True)

    amount: str
    currency: Literal["CNY", "USD"]
    fx_rate_used: str


class UpstreamPricingUpsert(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    provider: str = Field(min_length=1, max_length=50)
    upstream_model: str = Field(min_length=1, max_length=200)
    capability: str = Field(default="chat", max_length=40)
    currency: Literal["CNY", "USD"] = "CNY"
    amount_per_million: dict[str, Decimal | None] = Field(
        description="input / output / cache_creation / cache_read 每 1M tokens 展示币金额"
    )


class LitellmUpstreamSyncRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    providers: list[str] | None = Field(default=None, description="为空时使用已配置凭据提供商")


class EffectiveProviderResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    provider: str
    credential_count: int
    has_managed: bool
    has_user: bool


class UpstreamPricingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    upstream_model: str
    capability: str
    input_cost_per_token_usd: str
    output_cost_per_token_usd: str
    input_cost_per_million_display: MoneyDisplaySchema | None = None
    output_cost_per_million_display: MoneyDisplaySchema | None = None
    cache_creation_input_token_cost_usd: str | None = None
    cache_read_input_token_cost_usd: str | None = None
    effective_from: datetime
    effective_to: datetime | None
    version: int
    source: str
    display_currency: str | None = None
    fx_rate_used: str | None = None


class DownstreamPricingUpsert(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    scope: Literal["global", "team", "entitlement_plan"]
    scope_id: uuid.UUID | None = None
    gateway_model_id: uuid.UUID | None = None
    inheritance_strategy: Literal["mirror", "manual"] = "manual"
    currency: Literal["CNY", "USD"] = "CNY"
    amount_per_million: dict[str, Decimal | None] | None = None


class DownstreamPricingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    scope_id: uuid.UUID | None
    gateway_model_id: uuid.UUID | None
    inheritance_strategy: str
    input_cost_per_token_usd: str | None = None
    output_cost_per_token_usd: str | None = None
    input_cost_per_million_display: MoneyDisplaySchema | None = None
    output_cost_per_million_display: MoneyDisplaySchema | None = None
    effective_from: datetime
    effective_to: datetime | None
    version: int
    display_currency: str | None = None
    fx_rate_used: str | None = None


class PricingRateAdminView(BaseModel):
    """团队/平台管理员可见：含上游与毛利。"""

    model_config = ConfigDict(strict=True)

    gateway_model_id: uuid.UUID | None
    model_name: str | None
    downstream: DownstreamPricingResponse | None
    upstream: UpstreamPricingResponse | None
    margin_per_million_display: MoneyDisplaySchema | None = None
    hit_chain: list[str]


class PricingRateMemberView(BaseModel):
    """普通成员：仅下游生效价。"""

    model_config = ConfigDict(strict=True)

    gateway_model_id: uuid.UUID | None
    model_name: str | None
    input_cost_per_million_display: MoneyDisplaySchema | None = None
    output_cost_per_million_display: MoneyDisplaySchema | None = None
    inheritance_strategy: str | None = None
    display_currency: str


class SyncReportResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    created: int
    skipped: int


class PricingEstimateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    gateway_model_id: uuid.UUID
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    cache_read_tokens: int = Field(ge=0, default=0)


class PricingEstimateResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    gateway_model_id: str
    hit_chain: list[str]
    upstream_cost_usd: str
    downstream_revenue_usd: str
    margin_usd: str
    rate_snapshot: dict[str, object]
    disclaimer: str


class UpstreamPricingAuditResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    models_without_upstream: list[str]
    upstream_without_model: list[str]
    registered_upstream_keys: int


class LitellmUpstreamSyncReportResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    created: int
    updated: int
    skipped_manual: int


class PricingReconciliationResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    team_id: str
    period: str
    requests: int
    cost_usd: str
    revenue_usd: str
    margin_usd: str
    top_models: list[dict[str, object]]


class FxRateResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    usd_cny: str
    adapter: str = "static"
    default_display_currency: str


__all__ = [
    "DownstreamPricingResponse",
    "DownstreamPricingUpsert",
    "EffectiveProviderResponse",
    "FxRateResponse",
    "LitellmUpstreamSyncRequest",
    "MoneyDisplaySchema",
    "PricingRateAdminView",
    "PricingRateMemberView",
    "SyncReportResponse",
    "UpstreamPricingResponse",
    "UpstreamPricingUpsert",
]
