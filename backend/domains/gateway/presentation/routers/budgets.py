"""Budgets 子 router。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.schemas.common import (
    BudgetResponse,
    BudgetUpsert,
)
from domains.tenancy.domain.policies.team_role import is_team_admin_or_platform

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    team: CurrentTeam,
    reads: MgmtReads,
    target_kind: str | None = Query(
        default=None,
        pattern="^(system|tenant|key|user)$",
        description="Admin 可按 target_kind 过滤",
    ),
    model_name: str | None = Query(
        default=None,
        max_length=200,
        description="Admin 可按 model_name 精确过滤",
    ),
) -> list[BudgetResponse]:
    if is_team_admin_or_platform(team):
        budgets = await reads.list_budgets_for_team_admin(
            team.team_id,
            include_system=team.is_platform_admin,
            target_kind=target_kind,
            model_name=model_name,
        )
    else:
        budgets = await reads.list_budgets_for_tenant_and_user(
            team.team_id,
            team.user_id,
            actor_user_id=team.user_id,
        )
        if target_kind is not None:
            budgets = [b for b in budgets if b.target_kind == target_kind]
        normalized_model = (model_name or "").strip() or None
        if normalized_model is not None:
            budgets = [b for b in budgets if b.model_name == normalized_model]
    return [BudgetResponse.model_validate(b) for b in budgets]


@router.put("/budgets", response_model=BudgetResponse)
async def upsert_budget(
    body: BudgetUpsert,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> BudgetResponse:
    if body.target_kind == "tenant":
        body.target_id = team.team_id
    if body.target_kind == "user" and body.target_id is None:
        body.target_id = team.user_id
    if body.target_kind == "key" and body.target_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "key target requires target_id")
    if body.target_kind == "system" and not team.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only platform admin can set system budget")
    model_name = (body.model_name or "").strip() or None
    budget = await writes.upsert_budget(
        target_kind=body.target_kind,
        target_id=body.target_id,
        period=body.period,
        model_name=model_name,
        limit_usd=body.limit_usd,
        soft_limit_usd=body.soft_limit_usd,
        limit_tokens=body.limit_tokens,
        limit_requests=body.limit_requests,
    )
    return BudgetResponse.model_validate(budget)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_budget(
        budget_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )


__all__ = ["router"]
