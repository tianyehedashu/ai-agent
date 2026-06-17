"""ORM → 套餐只读模型映射（仅 application/infrastructure 边界使用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.management.plan_read_models import (
    EntitlementPlanReadModel,
    PlanQuotaReadModel,
    ProviderPlanReadModel,
)

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.entitlement_plan import (
        EntitlementPlan,
        EntitlementPlanQuota,
    )
    from domains.gateway.infrastructure.models.provider_plan import (
        ProviderPlan,
        ProviderPlanQuota,
    )


def _provider_quota_from_orm(row: ProviderPlanQuota) -> PlanQuotaReadModel:
    return PlanQuotaReadModel(
        id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        reset_strategy=row.reset_strategy,
        reset_timezone=row.reset_timezone,
        reset_time_minutes=row.reset_time_minutes,
        reset_day_of_month=row.reset_day_of_month,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
    )


def _entitlement_quota_from_orm(row: EntitlementPlanQuota) -> PlanQuotaReadModel:
    return PlanQuotaReadModel(
        id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        reset_strategy=row.reset_strategy,
        reset_timezone=row.reset_timezone,
        reset_time_minutes=row.reset_time_minutes,
        reset_day_of_month=row.reset_day_of_month,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        unit_price_usd_per_token=row.unit_price_usd_per_token,
        unit_price_usd_per_request=row.unit_price_usd_per_request,
    )


def provider_plan_from_orm(
    plan: ProviderPlan,
    quotas: list[ProviderPlanQuota],
) -> ProviderPlanReadModel:
    return ProviderPlanReadModel(
        id=plan.id,
        credential_id=plan.credential_id,
        real_model=plan.real_model,
        label=plan.label,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        is_active=plan.is_active,
        auto_renew=plan.auto_renew,
        notes=plan.notes,
        extra=plan.extra,
        quotas=tuple(_provider_quota_from_orm(q) for q in quotas),
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
        valid_until=plan.valid_until,
        included_models=tuple(plan.included_models or ()),
        included_capabilities=tuple(plan.included_capabilities or ()),
        is_active=plan.is_active,
        auto_renew=plan.auto_renew,
        notes=plan.notes,
        extra=plan.extra,
        quotas=tuple(_entitlement_quota_from_orm(q) for q in quotas),
    )


__all__ = ["entitlement_plan_from_orm", "provider_plan_from_orm"]
