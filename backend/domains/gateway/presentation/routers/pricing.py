"""定价目录 /api/v1/gateway/pricing/*"""

from __future__ import annotations

from typing import Annotated, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.pricing.pricing_catalog_reads import (
    PricingCatalogReadService,
    is_pricing_admin,
)
from domains.gateway.application.pricing.pricing_estimate_reads import estimate_usage_cost
from domains.gateway.application.pricing.pricing_management import (
    build_money_projector,
    upstream_row_to_response,
)
from domains.gateway.application.pricing.pricing_reconciliation_reads import (
    team_month_reconciliation,
)
from domains.gateway.application.pricing.pricing_service import RateUnavailableError
from domains.gateway.application.pricing.upstream_pricing_audit import (
    audit_upstream_pricing_keys,
)
from domains.gateway.application.pricing.upstream_sync_service import UpstreamSyncService
from domains.gateway.domain.money import DisplayCurrency
from domains.gateway.domain.types import normalize_downstream_pricing_scope
from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
    UpstreamPricingRepository,
)
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredGatewayAdmin,
    RequiredTeamAdmin,
    RequiredTeamMember,
)
from domains.gateway.presentation.schemas.pricing import (
    DownstreamPricingResponse,
    DownstreamPricingUpsert,
    EffectiveProviderResponse,
    FxRateResponse,
    LitellmUpstreamSyncReportResponse,
    LitellmUpstreamSyncRequest,
    PricingEstimateRequest,
    PricingEstimateResponse,
    PricingRateAdminView,
    PricingRateMemberView,
    PricingReconciliationResponse,
    SyncReportResponse,
    UpstreamPricingAuditResponse,
    UpstreamPricingResponse,
    UpstreamPricingUpsert,
)
from domains.identity.presentation.deps import RequiredAuthUser
from libs.db.database import get_db
from libs.exceptions import ValidationError

from ._common import MgmtWrites

router = APIRouter(prefix="/pricing", tags=["AI Gateway Pricing"])


def _parse_currency(raw: str | None) -> DisplayCurrency:
    if raw is None or raw.upper() == "CNY":
        return "CNY"
    if raw.upper() == "USD":
        return "USD"
    raise HTTPException(status_code=400, detail="currency must be CNY or USD")


def _catalog_reads(db: AsyncSession) -> PricingCatalogReadService:
    return PricingCatalogReadService(db)


def _sync_service(db: AsyncSession) -> UpstreamSyncService:
    return UpstreamSyncService(
        DownstreamPricingRepository(db),
        GatewayModelRepository(db),
    )


@router.get("/upstream/audit", response_model=UpstreamPricingAuditResponse)
async def audit_upstream_pricing(
    _admin: RequiredGatewayAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UpstreamPricingAuditResponse:
    report = await audit_upstream_pricing_keys(db)
    return UpstreamPricingAuditResponse.model_validate(report.to_dict())


@router.post(
    "/upstream/sync-from-litellm",
    response_model=LitellmUpstreamSyncReportResponse,
)
async def sync_upstream_from_litellm(
    _admin: RequiredGatewayAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    writes: MgmtWrites,
    body: LitellmUpstreamSyncRequest | None = None,
) -> LitellmUpstreamSyncReportResponse:
    report = await writes.sync_upstream_from_litellm(
        providers=body.providers if body is not None else None
    )
    await db.commit()
    return LitellmUpstreamSyncReportResponse.model_validate(report.to_dict())


@router.get("/effective-providers", response_model=list[EffectiveProviderResponse])
async def list_effective_pricing_providers(
    _admin: RequiredGatewayAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EffectiveProviderResponse]:
    rows = await _catalog_reads(db).list_effective_providers()
    return [EffectiveProviderResponse.model_validate(r) for r in rows]


@router.post("/estimate", response_model=PricingEstimateResponse)
async def estimate_pricing(
    body: PricingEstimateRequest,
    team: CurrentTeam,
    _member: RequiredTeamMember,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PricingEstimateResponse:
    try:
        payload = await estimate_usage_cost(
            db,
            team_id=team.team_id,
            gateway_model_id=body.gateway_model_id,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            cache_read_tokens=body.cache_read_tokens,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RateUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PricingEstimateResponse.model_validate(payload)


@router.get("/reconciliation", response_model=PricingReconciliationResponse)
async def pricing_reconciliation(
    team: CurrentTeam,
    admin: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> PricingReconciliationResponse:
    _ = admin
    payload = await team_month_reconciliation(db, team_id=team.team_id, year=year, month=month)
    return PricingReconciliationResponse.model_validate(payload)


@router.get("/fx", response_model=FxRateResponse)
async def get_fx_rates(
    _user: RequiredAuthUser,
) -> FxRateResponse:
    fx = build_static_fx_adapter()
    return FxRateResponse(
        usd_cny=str(fx.get_rate("USD", "CNY")),
        adapter="static",
        default_display_currency=fx.default_display_currency(),
    )


@router.get("/upstream", response_model=list[UpstreamPricingResponse])
async def list_upstream_pricing(
    _admin: RequiredGatewayAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    provider: str | None = Query(None),
    currency: str | None = Query("CNY"),
) -> list[UpstreamPricingResponse]:
    cur = _parse_currency(currency)
    fx = build_static_fx_adapter()
    projector = build_money_projector(fx)
    repo = UpstreamPricingRepository(db)
    rows = await repo.list_active(provider=provider)
    return [
        UpstreamPricingResponse.model_validate(
            upstream_row_to_response(r, projector=projector, currency=cur, fx=fx)
        )
        for r in rows
    ]


@router.post(
    "/upstream", response_model=UpstreamPricingResponse, status_code=status.HTTP_201_CREATED
)
async def create_upstream_pricing(
    body: UpstreamPricingUpsert,
    _admin: RequiredGatewayAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    writes: MgmtWrites,
) -> UpstreamPricingResponse:
    try:
        row = await writes.upsert_upstream_pricing(
            provider=body.provider,
            upstream_model=body.upstream_model,
            capability=body.capability,
            currency=body.currency,
            amount_per_million=body.amount_per_million,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cur = _parse_currency(body.currency)
    fx = build_static_fx_adapter()
    projector = build_money_projector(fx)
    return UpstreamPricingResponse.model_validate(
        upstream_row_to_response(row, projector=projector, currency=cur, fx=fx)
    )


@router.get("/downstream", response_model=list[DownstreamPricingResponse])
async def list_downstream_pricing(
    team: CurrentTeam,
    _member: RequiredTeamMember,
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: Literal["global", "team", "tenant", "entitlement_plan"] = Query("tenant"),
    scope_id: uuid.UUID | None = Query(None),
    currency: str | None = Query("CNY"),
) -> list[DownstreamPricingResponse]:
    cur = _parse_currency(currency)
    scope_norm = normalize_downstream_pricing_scope(scope)
    if scope_norm == "global" and not team.is_platform_admin:
        raise HTTPException(status_code=403, detail="global scope requires platform admin")
    sid = scope_id if scope_norm != "global" else None
    if scope_norm == "tenant" and sid is None:
        sid = team.team_id
    rows = await _catalog_reads(db).list_downstream(
        scope=scope_norm, scope_id=sid, currency=cur
    )
    return [DownstreamPricingResponse.model_validate(r) for r in rows]


@router.post(
    "/downstream", response_model=DownstreamPricingResponse, status_code=status.HTTP_201_CREATED
)
async def create_downstream_pricing(
    body: DownstreamPricingUpsert,
    team: CurrentTeam,
    admin: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    writes: MgmtWrites,
) -> DownstreamPricingResponse:
    _ = admin
    scope_norm = normalize_downstream_pricing_scope(body.scope)
    if scope_norm == "global" and not team.is_platform_admin:
        raise HTTPException(status_code=403, detail="global scope requires platform admin")
    sid = body.scope_id
    if scope_norm == "tenant" and sid is None:
        sid = team.team_id
    try:
        row = await writes.upsert_downstream_pricing(
            scope=scope_norm,
            scope_id=sid,
            gateway_model_id=body.gateway_model_id,
            inheritance_strategy=body.inheritance_strategy,
            currency=body.currency,
            amount_per_million=body.amount_per_million,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cur = _parse_currency(body.currency)
    payload = await _catalog_reads(db).list_downstream(
        scope=row.scope,
        scope_id=row.scope_id,
        currency=cur,
    )
    match = next((p for p in payload if p.get("id") == row.id), None)
    if match is not None:
        return DownstreamPricingResponse.model_validate(match)
    return DownstreamPricingResponse(
        id=row.id,
        scope=row.scope,
        scope_id=row.scope_id,
        gateway_model_id=row.gateway_model_id,
        inheritance_strategy=row.inheritance_strategy,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        version=row.version,
    )


@router.post("/downstream/sync", response_model=SyncReportResponse)
async def sync_downstream_from_upstream(
    team: CurrentTeam,
    _admin: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: Literal["team", "tenant", "entitlement_plan"] = Query("tenant"),
    scope_id: uuid.UUID | None = Query(None),
) -> SyncReportResponse:
    scope_norm = normalize_downstream_pricing_scope(scope)
    sid = scope_id or team.team_id
    svc = _sync_service(db)
    report = await svc.bulk_mirror_from_upstream(
        scope=scope_norm,
        scope_id=sid,
        team_id=team.team_id,
    )
    await db.commit()
    return SyncReportResponse(created=report.created, skipped=report.skipped)


@router.get("/my", response_model=list[PricingRateMemberView])
async def list_my_prices(
    team: CurrentTeam,
    user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: str | None = Query("CNY"),
) -> list[PricingRateMemberView]:
    _ = user
    cur = _parse_currency(currency)
    rows = await _catalog_reads(db).list_my_prices(team_id=team.team_id, currency=cur)
    return [PricingRateMemberView.model_validate(r) for r in rows]


@router.get("/resolve", response_model=PricingRateAdminView | PricingRateMemberView)
async def resolve_pricing(
    team: CurrentTeam,
    user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    gateway_model_id: uuid.UUID = Query(...),
    currency: str | None = Query("CNY"),
) -> PricingRateAdminView | PricingRateMemberView:
    _ = user
    cur = _parse_currency(currency)
    reads = _catalog_reads(db)
    try:
        payload = await reads.resolve_for_team(
            team=team,
            gateway_model_id=gateway_model_id,
            currency=cur,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RateUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if is_pricing_admin(team):
        return PricingRateAdminView.model_validate(payload)
    return PricingRateMemberView.model_validate(payload)
