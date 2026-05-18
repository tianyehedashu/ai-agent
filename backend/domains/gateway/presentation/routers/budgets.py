"""Budgets 子 router。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.schemas.common import (
    BudgetResponse,
    BudgetUpsert,
)

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[BudgetResponse]:
    budgets = await reads.list_budgets_for_team_and_user(team.team_id, team.user_id)
    return [BudgetResponse.model_validate(b) for b in budgets]


@router.put("/budgets", response_model=BudgetResponse)
async def upsert_budget(
    body: BudgetUpsert,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> BudgetResponse:
    if body.scope == "team":
        body.scope_id = team.team_id
    if body.scope == "user" and body.scope_id is None:
        body.scope_id = team.user_id
    if body.scope == "key" and body.scope_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "key scope requires scope_id")
    if body.scope == "system" and not team.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only platform admin can set system budget")
    model_name = (body.model_name or "").strip() or None
    budget = await writes.upsert_budget(
        scope=body.scope,
        scope_id=body.scope_id,
        period=body.period,
        model_name=model_name,
        limit_usd=body.limit_usd,
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
    _ = team
    await writes.delete_budget(budget_id)


__all__ = ["router"]
