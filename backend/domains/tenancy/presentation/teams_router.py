"""团队管理 HTTP（挂载在 ``/api/v1/gateway`` 下，路径与历史一致）。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.presentation.deps import RequiredAuthUser
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.presentation.schemas.teams import (
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
from domains.tenancy.presentation.team_dependencies import (
    RequiredTeamAdmin,
    RequiredTeamMember,
    RequiredTeamOwner,
)
from libs.db.database import get_db

router = APIRouter(tags=["Tenancy / Teams"])


def _team_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TeamService:
    return TeamService(db)


TeamSvc = Annotated[TeamService, Depends(_team_service)]


@router.get("/teams", response_model=list[TeamResponse])
async def list_my_teams(
    current_user: RequiredAuthUser,
    svc: TeamSvc,
) -> list[TeamResponse]:
    user_uuid = uuid.UUID(current_user.id)
    items_data = await svc.list_teams_with_roles_for_user(user_uuid)
    out: list[TeamResponse] = []
    for t, role in items_data:
        resp = TeamResponse.model_validate(t)
        resp.team_role = role
        out.append(resp)
    return out


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    current_user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    if current_user.is_anonymous:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anonymous cannot create team")
    team = await TeamService(db).create_team(
        name=body.name,
        owner_user_id=uuid.UUID(current_user.id),
        slug=body.slug,
        settings=body.settings,
    )
    return TeamResponse.model_validate(team)


@router.patch("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    team: RequiredTeamAdmin,
    svc: TeamSvc,
) -> TeamResponse:
    updated = await svc.update_team(team_id, name=body.name, settings=body.settings)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return TeamResponse.model_validate(updated)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    team: RequiredTeamOwner,
    svc: TeamSvc,
) -> None:
    record = await svc.get_team(team_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    if record.kind == "personal":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete personal team")
    try:
        await svc.delete_shared_team(team_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: uuid.UUID,
    team: RequiredTeamMember,
    svc: TeamSvc,
) -> list[TeamMemberResponse]:
    members = await svc.list_team_members(team_id)
    return [TeamMemberResponse.model_validate(m) for m in members]


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    team: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMemberResponse:
    member = await TeamService(db).add_member(team_id, body.user_id, body.role)
    return TeamMemberResponse.model_validate(member)


@router.delete("/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    team: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await TeamService(db).remove_member(team_id, user_id)
