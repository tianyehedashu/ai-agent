"""Provider Plans + Entitlement Plans 子 router。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, Query, status

from domains.gateway.presentation.deps import RequiredTeamAdmin
from domains.gateway.presentation.plan_response import entitlement_plan_to_response
from domains.gateway.presentation.schemas.common import (
    EntitlementPlanCreate,
    EntitlementPlanResponse,
    EntitlementPlanUpdate,
    EntitlementUsageResponse,
)
from libs.exceptions import AIAgentError, NotFoundError
from libs.exceptions.codes import INTERNAL_ERROR

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get(
    "/keys/{vkey_id}/entitlements",
    response_model=list[EntitlementPlanResponse],
)
async def list_vkey_entitlements(
    vkey_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[EntitlementPlanResponse]:
    await reads.access.assert_vkey_in_team(
        vkey_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    rows = await reads.list_entitlement_plans_with_quotas_for_scope("vkey", vkey_id)
    return [entitlement_plan_to_response(row) for row in rows]


@router.post(
    "/keys/{vkey_id}/entitlements",
    response_model=EntitlementPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vkey_entitlement(
    vkey_id: uuid.UUID,
    body: EntitlementPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    plan = await writes.create_entitlement_plan(
        scope="vkey",
        scope_id=vkey_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        label=body.label,
        valid_from=body.valid_from,
        included_models=body.included_models,
        included_capabilities=body.included_capabilities,
        notes=body.notes,
        extra=body.extra,
        quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
    )
    result = await reads.get_entitlement_plan_with_quotas(plan.id)
    if result is None:
        raise AIAgentError("plan not found", INTERNAL_ERROR)
    return entitlement_plan_to_response(result)


@router.patch(
    "/entitlements/{plan_id}",
    response_model=EntitlementPlanResponse,
)
async def update_entitlement_plan(
    plan_id: uuid.UUID,
    body: EntitlementPlanUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    quotas_raw = fields.pop("quotas", None)
    quotas_input = (
        [q if isinstance(q, dict) else q.model_dump(exclude_none=True) for q in quotas_raw]
        if quotas_raw is not None
        else None
    )
    await writes.update_entitlement_plan(
        plan_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        fields=fields,
        quotas=quotas_input,
    )
    result = await reads.get_entitlement_plan_with_quotas(plan_id)
    if result is None:
        raise NotFoundError("entitlement plan")
    return entitlement_plan_to_response(result)


@router.delete(
    "/entitlements/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entitlement_plan(
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_entitlement_plan(
        plan_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )


@router.get(
    "/entitlements/{plan_id}/usage",
    response_model=EntitlementUsageResponse,
)
async def get_entitlement_plan_usage(
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=180),
) -> EntitlementUsageResponse:
    await reads.access.assert_entitlement_plan_in_team(
        plan_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    usage = await reads.get_entitlement_usage(plan_id, since=start, until=end)
    return EntitlementUsageResponse(
        plan_id=usage.plan_id,
        period_start=usage.period_start,
        period_end=usage.period_end,
        requests=usage.requests,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=usage.cost_usd,
        charged_usd=usage.charged_usd,
    )


@router.get(
    "/api-key-grants/{grant_id}/entitlements",
    response_model=list[EntitlementPlanResponse],
)
async def list_apikey_grant_entitlements(
    grant_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[EntitlementPlanResponse]:
    await reads.access.assert_apikey_grant_in_team(
        grant_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    rows = await reads.list_entitlement_plans_with_quotas_for_scope("apikey_grant", grant_id)
    return [entitlement_plan_to_response(row) for row in rows]


@router.post(
    "/api-key-grants/{grant_id}/entitlements",
    response_model=EntitlementPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_apikey_grant_entitlement(
    grant_id: uuid.UUID,
    body: EntitlementPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    plan = await writes.create_entitlement_plan(
        scope="apikey_grant",
        scope_id=grant_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        label=body.label,
        valid_from=body.valid_from,
        included_models=body.included_models,
        included_capabilities=body.included_capabilities,
        notes=body.notes,
        extra=body.extra,
        quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
    )
    result = await reads.get_entitlement_plan_with_quotas(plan.id)
    if result is None:
        raise AIAgentError("plan not found", INTERNAL_ERROR)
    return entitlement_plan_to_response(result)


__all__ = ["router"]
