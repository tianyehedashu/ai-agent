"""Quota Rules 子 router（统一配额中心）。"""

from __future__ import annotations

from typing import Annotated, Literal, cast
import uuid

from fastapi import APIRouter, Depends, Query, status

from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleLayer,
    QuotaRuleListFilters,
)
from domains.gateway.application.management.quota_usage_adjustment import (
    QuotaUsageAdjustmentCommand,
)
from domains.gateway.application.management.write_modules.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from domains.gateway.presentation.deps import CurrentTeam, RequiredTeamAdmin
from domains.gateway.presentation.quota_rule_list_response import build_quota_rule_list_response
from domains.gateway.presentation.quota_rule_response import quota_rule_to_response
from domains.gateway.presentation.schemas.common import (
    QuotaRuleBatchFailureItem,
    QuotaRuleBatchUpsertRequest,
    QuotaRuleBatchUpsertResponse,
    QuotaRuleEnablementRequest,
    QuotaRuleListResponse,
    QuotaRuleResponse,
    QuotaRuleUpsert,
    QuotaUsageAdjustmentRequest,
)
from domains.tenancy.domain.policies.team_role import is_team_admin_or_platform
from libs.api.pagination import PageParams, page_query_params

from ._common import MgmtReads, MgmtWrites

router = APIRouter()

PageDep = Annotated[PageParams, Depends(page_query_params)]


@router.get("/quota-rules", response_model=QuotaRuleListResponse)
async def list_quota_rules(
    team: CurrentTeam,
    reads: MgmtReads,
    page: PageDep,
    layer: str | None = Query(
        default=None,
        pattern="^(platform|upstream|downstream)$",
    ),
    user_id: uuid.UUID | None = Query(default=None),
    credential_id: uuid.UUID | None = Query(default=None),
    model_name: str | None = Query(default=None, max_length=200),
    period: str | None = Query(default=None, pattern="^(daily|monthly|total)$"),
    include_usage: bool = Query(default=False),
) -> QuotaRuleListResponse:
    filters = QuotaRuleListFilters(
        layer=cast("QuotaRuleLayer | None", layer),
        user_id=user_id,
        credential_id=credential_id,
        model_name=(model_name or "").strip() or None,
        period=period,
    )
    rows, total = await reads.list_quota_rules_for_team(
        team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
        is_team_admin=is_team_admin_or_platform(team),
        filters=filters,
        include_usage=include_usage,
        page=page.page,
        page_size=page.page_size,
    )
    return build_quota_rule_list_response(
        rows=rows,
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


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


@router.delete("/quota-rules/plan", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_quota(
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    layer: str = Query(pattern="^(upstream|downstream)$"),
    quota_id: uuid.UUID = Query(),
    plan_id: uuid.UUID | None = Query(default=None),
) -> None:
    """团队管理员：删除单条上游 / 下游配额（下游删空套餐时连带删空 plan 头）。"""
    await writes.delete_plan_quota(
        layer=cast("Literal['upstream', 'downstream']", layer),
        plan_id=plan_id,
        quota_id=quota_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=team.is_platform_admin,
        is_team_admin=is_team_admin_or_platform(team),
    )


@router.delete("/quota-rules/self/plan", status_code=status.HTTP_204_NO_CONTENT)
async def delete_self_plan_quota(
    team: CurrentTeam,
    writes: MgmtWrites,
    quota_id: uuid.UUID = Query(),
    plan_id: uuid.UUID | None = Query(default=None),
) -> None:
    """成员自助：删除本人凭据上的单条上游配额。"""
    await writes.delete_plan_quota(
        layer="upstream",
        plan_id=plan_id,
        quota_id=quota_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=False,
        is_team_admin=False,
        member_self_service=True,
    )


@router.post("/quota-rules/usage-adjustments", response_model=QuotaRuleResponse)
async def adjust_quota_rule_usage(
    body: QuotaUsageAdjustmentRequest,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> QuotaRuleResponse:
    """团队管理员：手工设置当前周期已用额度或清零本窗口。"""
    row = await writes.adjust_quota_rule_usage(
        _adjustment_to_command(body),
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=team.is_platform_admin,
        is_team_admin=is_team_admin_or_platform(team),
    )
    return quota_rule_to_response(row)


@router.post("/quota-rules/enablement", response_model=QuotaRuleResponse)
async def set_quota_rule_enablement(
    body: QuotaRuleEnablementRequest,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> QuotaRuleResponse:
    """团队管理员：启用 / 停用单条配额规则。"""
    row = await writes.set_quota_rule_enabled(
        layer=body.layer,
        budget_id=body.budget_id,
        plan_id=body.plan_id,
        quota_id=body.quota_id,
        enabled=body.enabled,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=team.is_platform_admin,
        is_team_admin=is_team_admin_or_platform(team),
    )
    return quota_rule_to_response(row)


@router.post("/quota-rules/self/enablement", response_model=QuotaRuleResponse)
async def set_self_quota_rule_enablement(
    body: QuotaRuleEnablementRequest,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> QuotaRuleResponse:
    """成员自助：启用 / 停用本人平台或本人凭据上游配额规则。"""
    row = await writes.set_quota_rule_enabled(
        layer=body.layer,
        budget_id=body.budget_id,
        plan_id=body.plan_id,
        quota_id=body.quota_id,
        enabled=body.enabled,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=False,
        is_team_admin=False,
        member_self_service=True,
    )
    return quota_rule_to_response(row)


@router.post("/quota-rules/self/usage-adjustments", response_model=QuotaRuleResponse)
async def adjust_self_quota_rule_usage(
    body: QuotaUsageAdjustmentRequest,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> QuotaRuleResponse:
    """成员自助：调整本人平台或本人凭据上游配额的已用额度。"""
    row = await writes.adjust_quota_rule_usage(
        _adjustment_to_command(body),
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=False,
        is_team_admin=False,
        member_self_service=True,
    )
    return quota_rule_to_response(row)


def _adjustment_to_command(body: QuotaUsageAdjustmentRequest) -> QuotaUsageAdjustmentCommand:
    return QuotaUsageAdjustmentCommand(
        layer=body.layer,
        budget_id=body.budget_id,
        plan_id=body.plan_id,
        quota_id=body.quota_id,
        mode=body.mode,
        current_usd=body.current_usd,
        current_tokens=body.current_tokens,
        current_requests=body.current_requests,
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
        period_timezone=body.period_timezone,
        period_reset_minutes=body.period_reset_minutes,
        period_reset_day=body.period_reset_day,
        reset_timezone=body.reset_timezone,
        reset_time_minutes=body.reset_time_minutes,
        reset_day_of_month=body.reset_day_of_month,
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
        enabled=body.enabled,
    )


__all__ = ["router"]
