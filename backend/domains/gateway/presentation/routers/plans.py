"""Provider Plans + Entitlement Plans 子 router。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from domains.gateway.infrastructure.models.entitlement_plan import (
    EntitlementPlan,
    EntitlementPlanQuota,
)
from domains.gateway.infrastructure.models.provider_plan import (
    ProviderPlan,
    ProviderPlanQuota,
)
from domains.gateway.presentation.deps import RequiredTeamAdmin
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    EntitlementPlanCreate,
    EntitlementPlanQuotaResponse,
    EntitlementPlanResponse,
    EntitlementPlanUpdate,
    EntitlementUsageResponse,
    PlanQuotaResponse,
    ProviderPlanCostResponse,
    ProviderPlanCreate,
    ProviderPlanResponse,
    ProviderPlanUpdate,
)
from libs.exceptions import HttpMappableDomainError

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


def _provider_plan_to_response(
    plan: ProviderPlan, quotas: list[ProviderPlanQuota]
) -> ProviderPlanResponse:
    return ProviderPlanResponse(
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
        quotas=[PlanQuotaResponse.model_validate(q) for q in quotas],
    )


def _entitlement_plan_to_response(
    plan: EntitlementPlan, quotas: list[EntitlementPlanQuota]
) -> EntitlementPlanResponse:
    return EntitlementPlanResponse(
        id=plan.id,
        scope=plan.scope,
        scope_id=plan.scope_id,
        label=plan.label,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        included_models=list(plan.included_models or []),
        included_capabilities=list(plan.included_capabilities or []),
        is_active=plan.is_active,
        auto_renew=plan.auto_renew,
        notes=plan.notes,
        extra=plan.extra,
        quotas=[EntitlementPlanQuotaResponse.model_validate(q) for q in quotas],
    )


@router.get(
    "/credentials/{credential_id}/provider-plans",
    response_model=list[ProviderPlanResponse],
)
async def list_provider_plans(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[ProviderPlanResponse]:
    try:
        await reads.assert_credential_in_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_provider_plans_with_quotas_for_credential(credential_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_provider_plan_to_response(plan, quotas) for plan, quotas in rows]


@router.post(
    "/credentials/{credential_id}/provider-plans",
    response_model=ProviderPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_plan(
    credential_id: uuid.UUID,
    body: ProviderPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> ProviderPlanResponse:
    try:
        plan = await writes.create_provider_plan(
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            real_model=body.real_model,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_provider_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found after create"
        )
    return _provider_plan_to_response(*result)


@router.patch(
    "/credentials/{credential_id}/provider-plans/{plan_id}",
    response_model=ProviderPlanResponse,
)
async def update_provider_plan(
    credential_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: ProviderPlanUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> ProviderPlanResponse:
    try:
        fields = body.model_dump(exclude_unset=True, exclude_none=True)
        quotas_raw = fields.pop("quotas", None)
        quotas_input = (
            [q if isinstance(q, dict) else q.model_dump(exclude_none=True) for q in quotas_raw]
            if quotas_raw is not None
            else None
        )
        await writes.update_provider_plan(
            plan_id,
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            fields=fields,
            quotas=quotas_input,
        )
        result = await reads.get_provider_plan_with_quotas(plan_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="provider plan not found")
    return _provider_plan_to_response(*result)


@router.delete(
    "/credentials/{credential_id}/provider-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider_plan(
    credential_id: uuid.UUID,
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_provider_plan(
            plan_id,
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.get(
    "/credentials/{credential_id}/provider-plan-usage",
    response_model=list[ProviderPlanCostResponse],
)
async def list_provider_plan_usage(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=180),
) -> list[ProviderPlanCostResponse]:
    try:
        await reads.assert_credential_in_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_provider_plans_with_quotas_for_credential(credential_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    out: list[ProviderPlanCostResponse] = []
    for plan, _quotas in rows:
        usage = await reads.get_provider_plan_cost(plan.id, since=start, until=end)
        out.append(
            ProviderPlanCostResponse(
                plan_id=usage.plan_id,
                period_start=usage.period_start,
                period_end=usage.period_end,
                requests=usage.requests,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
            )
        )
    return out


@router.get(
    "/keys/{vkey_id}/entitlements",
    response_model=list[EntitlementPlanResponse],
)
async def list_vkey_entitlements(
    vkey_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[EntitlementPlanResponse]:
    try:
        await reads.assert_vkey_in_team(
            vkey_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_entitlement_plans_with_quotas_for_scope("vkey", vkey_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_entitlement_plan_to_response(plan, quotas) for plan, quotas in rows]


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
    try:
        plan = await writes.create_entitlement_plan(
            scope="vkey",
            scope_id=vkey_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            included_models=body.included_models,
            included_capabilities=body.included_capabilities,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_entitlement_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found")
    return _entitlement_plan_to_response(*result)


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
    try:
        fields = body.model_dump(exclude_unset=True, exclude_none=True)
        quotas_raw = fields.pop("quotas", None)
        quotas_input = (
            [q if isinstance(q, dict) else q.model_dump(exclude_none=True) for q in quotas_raw]
            if quotas_raw is not None
            else None
        )
        await writes.update_entitlement_plan(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            fields=fields,
            quotas=quotas_input,
        )
        result = await reads.get_entitlement_plan_with_quotas(plan_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="entitlement plan not found")
    return _entitlement_plan_to_response(*result)


@router.delete(
    "/entitlements/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entitlement_plan(
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_entitlement_plan(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


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
    try:
        await reads.assert_entitlement_plan_in_team(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
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
    try:
        await reads.assert_apikey_grant_in_team(
            grant_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_entitlement_plans_with_quotas_for_scope(
            "apikey_grant", grant_id
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_entitlement_plan_to_response(plan, quotas) for plan, quotas in rows]


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
    try:
        plan = await writes.create_entitlement_plan(
            scope="apikey_grant",
            scope_id=grant_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            included_models=body.included_models,
            included_capabilities=body.included_capabilities,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_entitlement_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found")
    return _entitlement_plan_to_response(*result)


__all__ = ["router"]
