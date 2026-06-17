"""QuotaRuleReadModel → HTTP Schema 映射。"""

from __future__ import annotations

from domains.gateway.application.management.quota_rule_read_model import QuotaRuleReadModel
from domains.gateway.presentation.schemas.common import (
    QuotaRuleKeyResponse,
    QuotaRuleLimitsResponse,
    QuotaRuleResponse,
    QuotaRuleSourceRefResponse,
    QuotaRuleUsageResponse,
)


def quota_rule_to_response(model: QuotaRuleReadModel) -> QuotaRuleResponse:
    usage = None
    if model.usage is not None:
        usage = QuotaRuleUsageResponse(
            current_usd=model.usage.current_usd,
            current_tokens=model.usage.current_tokens,
            current_requests=model.usage.current_requests,
            reset_at=model.usage.reset_at,
            budget_reset_at=model.usage.budget_reset_at,
        )
    return QuotaRuleResponse(
        key=QuotaRuleKeyResponse(
            team_id=model.key.team_id,
            layer=model.key.layer,
            user_id=model.key.user_id,
            credential_id=model.key.credential_id,
            model_name=model.key.model_name,
            period=model.key.period,
            window_seconds=model.key.window_seconds,
            reset_strategy=model.key.reset_strategy,
            period_timezone=model.key.period_timezone,
            period_reset_minutes=model.key.period_reset_minutes,
            period_reset_day=model.key.period_reset_day,
            access_kind=model.key.access_kind,
            access_id=model.key.access_id,
            quota_label=model.key.quota_label,
            target_kind=model.key.target_kind,
            target_id=model.key.target_id,
        ),
        source_ref=QuotaRuleSourceRefResponse(
            layer=model.source_ref.layer,
            budget_id=model.source_ref.budget_id,
            plan_id=model.source_ref.plan_id,
            quota_id=model.source_ref.quota_id,
        ),
        limits=QuotaRuleLimitsResponse(
            limit_usd=model.limits.limit_usd,
            soft_limit_usd=model.limits.soft_limit_usd,
            limit_tokens=model.limits.limit_tokens,
            limit_requests=model.limits.limit_requests,
            unit_price_usd_per_token=model.limits.unit_price_usd_per_token,
            unit_price_usd_per_request=model.limits.unit_price_usd_per_request,
        ),
        usage=usage,
        plan_label=model.plan_label,
        is_active=model.is_active,
    )


__all__ = ["quota_rule_to_response"]
