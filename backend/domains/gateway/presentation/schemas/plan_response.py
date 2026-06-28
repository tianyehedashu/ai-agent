"""套餐读模型 → HTTP Response（presentation 层，不依赖 ORM）。"""

from __future__ import annotations

from domains.gateway.application.quota.management.plan_read_model import EntitlementPlanReadModel
from domains.gateway.presentation.schemas.common import (
    EntitlementPlanQuotaResponse,
    EntitlementPlanResponse,
)


def entitlement_plan_to_response(model: EntitlementPlanReadModel) -> EntitlementPlanResponse:
    # plan 头已退化为容器；有效期 / 活性由 quota 行承载，响应不再暴露 valid_until / is_active / auto_renew。
    return EntitlementPlanResponse(
        id=model.id,
        scope=model.scope,
        scope_id=model.scope_id,
        label=model.label,
        valid_from=model.valid_from,
        included_models=list(model.included_models),
        included_capabilities=list(model.included_capabilities),
        notes=model.notes,
        extra=model.extra,
        quotas=[EntitlementPlanQuotaResponse.model_validate(q) for q in model.quotas],
    )


__all__ = ["entitlement_plan_to_response"]
