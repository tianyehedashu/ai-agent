"""套餐读模型 → HTTP Response（presentation 层，不依赖 ORM）。"""

from __future__ import annotations

from domains.gateway.application.management.plan_read_models import (
    EntitlementPlanReadModel,
    ProviderPlanReadModel,
)
from domains.gateway.presentation.schemas.common import (
    EntitlementPlanQuotaResponse,
    EntitlementPlanResponse,
    PlanQuotaResponse,
    ProviderPlanResponse,
)


def provider_plan_to_response(model: ProviderPlanReadModel) -> ProviderPlanResponse:
    return ProviderPlanResponse(
        id=model.id,
        credential_id=model.credential_id,
        real_model=model.real_model,
        label=model.label,
        valid_from=model.valid_from,
        valid_until=model.valid_until,
        is_active=model.is_active,
        auto_renew=model.auto_renew,
        notes=model.notes,
        extra=model.extra,
        quotas=[
            PlanQuotaResponse.model_validate(q)
            for q in model.quotas
        ],
    )


def entitlement_plan_to_response(model: EntitlementPlanReadModel) -> EntitlementPlanResponse:
    return EntitlementPlanResponse(
        id=model.id,
        scope=model.scope,
        scope_id=model.scope_id,
        label=model.label,
        valid_from=model.valid_from,
        valid_until=model.valid_until,
        included_models=list(model.included_models),
        included_capabilities=list(model.included_capabilities),
        is_active=model.is_active,
        auto_renew=model.auto_renew,
        notes=model.notes,
        extra=model.extra,
        quotas=[
            EntitlementPlanQuotaResponse.model_validate(q)
            for q in model.quotas
        ],
    )


__all__ = ["entitlement_plan_to_response", "provider_plan_to_response"]
