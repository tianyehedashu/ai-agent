"""配额规则统一读模型（管理面 Query，非运行时领域实体）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

QuotaRuleLayer = Literal["platform", "upstream", "downstream"]
QuotaRuleAccessKind = Literal["none", "vkey", "apikey_grant"]


@dataclass(frozen=True)
class QuotaRuleKey:
    team_id: UUID
    layer: QuotaRuleLayer
    user_id: UUID | None
    credential_id: UUID | None
    model_name: str | None
    period: str | None
    window_seconds: int | None
    reset_strategy: str | None
    access_kind: QuotaRuleAccessKind
    access_id: UUID | None
    quota_label: str | None
    target_kind: str | None
    target_id: UUID | None
    period_timezone: str | None = None
    period_reset_minutes: int | None = None
    period_reset_day: int | None = None


@dataclass(frozen=True)
class QuotaRuleSourceRef:
    layer: QuotaRuleLayer
    budget_id: UUID | None = None
    plan_id: UUID | None = None
    quota_id: UUID | None = None


@dataclass(frozen=True)
class QuotaRuleLimits:
    limit_usd: Decimal | None
    soft_limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    unit_price_usd_per_token: Decimal | None = None
    unit_price_usd_per_request: Decimal | None = None


@dataclass(frozen=True)
class QuotaRuleUsage:
    current_usd: Decimal | None = None
    current_tokens: int | None = None
    current_requests: int | None = None
    window_start: datetime | None = None
    reset_at: datetime | None = None
    budget_reset_at: datetime | None = None


@dataclass(frozen=True)
class QuotaRuleReadModel:
    key: QuotaRuleKey
    source_ref: QuotaRuleSourceRef
    limits: QuotaRuleLimits
    usage: QuotaRuleUsage | None
    plan_label: str | None
    is_active: bool
    plan_valid_from: datetime | None = None
    # 按行（规则）维度的起止时间；NULL 表示该侧不限。is_active 即「启用停用」。
    valid_from: datetime | None = None
    valid_until: datetime | None = None


@dataclass(frozen=True)
class QuotaRuleListFilters:
    layer: QuotaRuleLayer | None = None
    user_id: UUID | None = None
    credential_id: UUID | None = None
    model_name: str | None = None
    period: str | None = None


__all__ = [
    "QuotaRuleAccessKind",
    "QuotaRuleKey",
    "QuotaRuleLayer",
    "QuotaRuleLimits",
    "QuotaRuleListFilters",
    "QuotaRuleReadModel",
    "QuotaRuleSourceRef",
    "QuotaRuleUsage",
]
