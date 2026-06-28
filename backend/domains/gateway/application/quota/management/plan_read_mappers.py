"""ORM → 套餐只读模型映射（仅 application/infrastructure 边界使用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.quota.period_reset_anchor import period_reset_anchor_from_plan_quota
from domains.gateway.domain.quota.quota_plan import (
    PlanQuotaSpec,
    normalize_reset_strategy,
)

from .plan_read_model import (
    EntitlementPlanReadModel,
    PlanQuotaReadModel,
    ProviderQuotaReadModel,
)

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.entitlement_plan import (
        EntitlementPlan,
        EntitlementPlanQuota,
    )
    from domains.gateway.infrastructure.models.provider_quota import ProviderQuota


def _entitlement_quota_from_orm(row: EntitlementPlanQuota) -> PlanQuotaReadModel:
    return PlanQuotaReadModel(
        id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        reset_timezone=row.reset_timezone,
        reset_time_minutes=row.reset_time_minutes,
        reset_day_of_month=row.reset_day_of_month,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        unit_price_usd_per_token=row.unit_price_usd_per_token,
        unit_price_usd_per_request=row.unit_price_usd_per_request,
        enabled=row.enabled,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        limit_images=getattr(row, "limit_images", None),
    )


def provider_quota_from_orm(row: ProviderQuota) -> ProviderQuotaReadModel:
    return ProviderQuotaReadModel(
        id=row.id,
        credential_id=row.credential_id,
        real_model=row.real_model,
        label=row.label,
        window_seconds=row.window_seconds,
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        reset_timezone=row.reset_timezone,
        reset_time_minutes=row.reset_time_minutes,
        reset_day_of_month=row.reset_day_of_month,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        enabled=row.enabled,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        limit_images=getattr(row, "limit_images", None),
    )


def provider_quota_to_spec(row: ProviderQuota) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        limit_images=getattr(row, "limit_images", None),
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        period_reset_anchor=period_reset_anchor_from_plan_quota(
            reset_timezone=row.reset_timezone,
            reset_time_minutes=row.reset_time_minutes,
            reset_day_of_month=row.reset_day_of_month,
        ),
    )


def entitlement_plan_quota_to_spec(row: EntitlementPlanQuota) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        limit_images=getattr(row, "limit_images", None),
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        period_reset_anchor=period_reset_anchor_from_plan_quota(
            reset_timezone=row.reset_timezone,
            reset_time_minutes=row.reset_time_minutes,
            reset_day_of_month=row.reset_day_of_month,
        ),
    )


def entitlement_plan_from_orm(
    plan: EntitlementPlan,
    quotas: list[EntitlementPlanQuota],
) -> EntitlementPlanReadModel:
    return EntitlementPlanReadModel(
        id=plan.id,
        scope=plan.target_kind,
        scope_id=plan.target_id,
        label=plan.label,
        valid_from=plan.valid_from,
        included_models=tuple(plan.included_models or ()),
        included_capabilities=tuple(plan.included_capabilities or ()),
        notes=plan.notes,
        extra=plan.extra,
        quotas=tuple(_entitlement_quota_from_orm(q) for q in quotas),
    )


__all__ = [
    "entitlement_plan_from_orm",
    "entitlement_plan_quota_to_spec",
    "provider_quota_from_orm",
    "provider_quota_to_spec",
]
