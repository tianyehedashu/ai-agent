"""Alerts 子 router。"""

from __future__ import annotations

from decimal import Decimal
import uuid

from fastapi import APIRouter, Query, status

from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.schemas.common import (
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from domains.gateway.presentation.tenant_scoped_response import (
    apply_tenant_team_mirror,
    tenant_scoped_orm_dict,
)

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get("/alerts/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[AlertRuleResponse]:
    rows = await reads.list_alert_rules(team.team_id)
    return [
        AlertRuleResponse.model_validate(
            apply_tenant_team_mirror(
                {
                    "id": r.id,
                    "tenant_id": r.tenant_id,
                    "name": r.name,
                    "description": r.description,
                    "metric": r.metric,
                    "threshold": r.threshold,
                    "window_minutes": r.window_minutes,
                    "channels": r.channels,
                    "enabled": r.enabled,
                    "last_triggered_at": r.last_triggered_at,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
            )
        )
        for r in rows
    ]


@router.post("/alerts/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    body: AlertRuleCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> AlertRuleResponse:
    rule = await writes.create_alert_rule(
        tenant_id=team.team_id,
        name=body.name,
        description=body.description,
        metric=body.metric,
        threshold=Decimal(str(body.threshold)),
        window_minutes=body.window_minutes,
        channels=body.channels,
        enabled=body.enabled,
    )
    return AlertRuleResponse.model_validate(tenant_scoped_orm_dict(rule))


@router.patch("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> AlertRuleResponse:
    rule = await writes.update_alert_rule(
        rule_id,
        tenant_id=team.team_id,
        fields=body.model_dump(exclude_unset=True, exclude_none=True),
    )
    return AlertRuleResponse.model_validate(tenant_scoped_orm_dict(rule))


@router.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_alert_rule(rule_id, tenant_id=team.team_id)


@router.get("/alerts/events", response_model=list[AlertEventResponse])
async def list_alert_events(
    team: CurrentTeam,
    reads: MgmtReads,
    limit: int = Query(100, ge=1, le=500),
) -> list[AlertEventResponse]:
    rows = await reads.list_alert_events_as_dicts(team.team_id, limit=limit)
    return [AlertEventResponse.model_validate(apply_tenant_team_mirror(dict(row))) for row in rows]


__all__ = ["router"]
