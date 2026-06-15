"""Quota Rules 子 router（统一配额中心）。"""

from __future__ import annotations

from typing import cast
import uuid

from fastapi import APIRouter, Query, status

from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleLayer,
    QuotaRuleListFilters,
)
from domains.gateway.application.management.write_modules.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from domains.gateway.presentation.deps import CurrentTeam, RequiredTeamAdmin
from domains.gateway.presentation.quota_rule_response import quota_rule_to_response
from domains.gateway.presentation.schemas.common import (
    QuotaRuleBatchFailureItem,
    QuotaRuleBatchUpsertRequest,
    QuotaRuleBatchUpsertResponse,
    QuotaRuleResponse,
    QuotaRuleUpsert,
)
from domains.tenancy.domain.policies.team_role import is_team_admin_or_platform

from ._common import MgmtReads, MgmtWrites

router = APIRouter()


@router.get("/quota-rules", response_model=list[QuotaRuleResponse])
async def list_quota_rules(
    team: CurrentTeam,
    reads: MgmtReads,
    layer: str | None = Query(
        default=None,
        pattern="^(platform|upstream|downstream)$",
    ),
    user_id: uuid.UUID | None = Query(default=None),
    credential_id: uuid.UUID | None = Query(default=None),
    model_name: str | None = Query(default=None, max_length=200),
    period: str | None = Query(default=None, pattern="^(daily|monthly|total)$"),
    include_usage: bool = Query(default=False),
) -> list[QuotaRuleResponse]:
    filters = QuotaRuleListFilters(
        layer=cast("QuotaRuleLayer | None", layer),
        user_id=user_id,
        credential_id=credential_id,
        model_name=(model_name or "").strip() or None,
        period=period,
    )
    rows = await reads.list_quota_rules_for_team(
        team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
        is_team_admin=is_team_admin_or_platform(team),
        filters=filters,
        include_usage=include_usage,
    )
    return [quota_rule_to_response(row) for row in rows]


@router.put("/quota-rules/batch", response_model=QuotaRuleBatchUpsertResponse)
async def batch_upsert_quota_rules(
    body: QuotaRuleBatchUpsertRequest,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> QuotaRuleBatchUpsertResponse:
    commands = [_upsert_to_command(item) for item in body.rules]
    result = await writes.batch_upsert_quota_rules(
        commands,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        actor_user_id=team.user_id,
    )
    return QuotaRuleBatchUpsertResponse(
        succeeded=[quota_rule_to_response(row) for row in result.succeeded],
        failed=[
            QuotaRuleBatchFailureItem(index=item.index, error=item.error) for item in result.failed
        ],
    )


@router.put("/quota-rules/self-batch", response_model=QuotaRuleBatchUpsertResponse)
async def batch_upsert_self_quota_rules(
    body: QuotaRuleBatchUpsertRequest,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> QuotaRuleBatchUpsertResponse:
    """成员自助：写本人 platform 配额或本人 BYOK 的 upstream 厂商额度。"""
    commands = [_upsert_to_command(item) for item in body.rules]
    result = await writes.batch_upsert_self_quota_rules(
        commands,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
    )
    return QuotaRuleBatchUpsertResponse(
        succeeded=[quota_rule_to_response(row) for row in result.succeeded],
        failed=[
            QuotaRuleBatchFailureItem(index=item.index, error=item.error) for item in result.failed
        ],
    )


@router.delete("/quota-rules/self/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_self_quota_rule(
    budget_id: uuid.UUID,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> None:
    """成员自助：删除本人「user + 本人凭据」的平台配额行。"""
    await writes.delete_self_budget(
        budget_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
    )


def _upsert_to_command(body: QuotaRuleUpsert) -> QuotaRuleUpsertCommand:
    model_name = (body.model_name or "").strip() or None
    return QuotaRuleUpsertCommand(
        layer=body.layer,
        target_kind=body.target_kind,
        target_id=body.target_id,
        user_id=body.user_id,
        credential_id=body.credential_id,
        model_name=model_name,
        period=body.period,
        window_seconds=body.window_seconds,
        reset_strategy=body.reset_strategy,
        quota_label=body.quota_label,
        access_kind=body.access_kind,
        access_id=body.access_id,
        included_models=body.included_models,
        limit_usd=body.limit_usd,
        soft_limit_usd=body.soft_limit_usd,
        limit_tokens=body.limit_tokens,
        limit_requests=body.limit_requests,
        unit_price_usd_per_token=body.unit_price_usd_per_token,
        unit_price_usd_per_request=body.unit_price_usd_per_request,
        plan_label=body.plan_label,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )


__all__ = ["router"]
