"""套餐读模型 → HTTP Response（presentation 层，不依赖 ORM）。"""

from __future__ import annotations

from datetime import UTC, datetime

from domains.gateway.application.management.plan_read_models import EntitlementPlanReadModel
from domains.gateway.presentation.schemas.common import (
    EntitlementPlanQuotaResponse,
    EntitlementPlanResponse,
)


def entitlement_plan_to_response(model: EntitlementPlanReadModel) -> EntitlementPlanResponse:
    # plan 头已退化为容器；valid_until / is_active 由 quota 行承载，响应字段保留兼容默认值。
    return EntitlementPlanResponse(
        id=model.id,
        scope=model.scope,
        scope_id=model.scope_id,
        label=model.label,
        valid_from=model.valid_from,
        valid_until=datetime.max.replace(tzinfo=UTC),
        included_models=list(model.included_models),
        included_capabilities=list(model.included_capabilities),
        is_active=True,
        auto_renew=False,
        notes=model.notes,
        extra=model.extra,
        quotas=[EntitlementPlanQuotaResponse.model_validate(q) for q in model.quotas],
    )


__all__ = ["entitlement_plan_to_response"]
