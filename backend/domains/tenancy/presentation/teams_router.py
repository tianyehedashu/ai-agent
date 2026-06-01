"""团队管理 HTTP（挂载在 ``/api/v1/gateway`` 下，路径与历史一致）。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.user_use_case import UserUseCase
from domains.identity.domain.rbac import Role
from domains.identity.presentation.deps import RequiredAuthUser
from domains.tenancy.application.team_invite_candidate_reads import TeamInviteCandidateReads
from domains.tenancy.application.team_member_reads import EnrichedTeamMember, enrich_team_members
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.presentation.schemas.teams import (
    TeamCreate,
    TeamInviteCandidateListResponse,
    TeamMemberAdd,
    TeamMemberLookupResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
from domains.tenancy.presentation.team_dependencies import (
    RequiredTeamAdmin,
    RequiredTeamMember,
    RequiredTeamOwner,
)
from domains.tenancy.presentation.team_invite_mappers import to_invite_candidate_list_response
from libs.api.pagination import PageParams, page_query_params
from libs.db.database import get_db
from libs.exceptions import NotFoundError, ValidationError
from libs.identity_bridge_deps import create_user_use_case, get_user_use_case

router = APIRouter(tags=["Tenancy / Teams"])


def _team_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TeamService:
    return TeamService(db)


TeamSvc = Annotated[TeamService, Depends(_team_service)]
UserSvc = Annotated[UserUseCase, Depends(get_user_use_case)]
PageDep = Annotated[PageParams, Depends(page_query_params)]


def _invite_candidate_reads(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamInviteCandidateReads:
    return TeamInviteCandidateReads(create_user_use_case(db))


InviteReads = Annotated[TeamInviteCandidateReads, Depends(_invite_candidate_reads)]


def _to_member_responses(
    enriched: list[EnrichedTeamMember],
) -> list[TeamMemberResponse]:
    return [TeamMemberResponse.model_validate(item) for item in enriched]


@router.get("/teams", response_model=list[TeamResponse])
async def list_my_teams(
    current_user: RequiredAuthUser,
    svc: TeamSvc,
    user_service: UserSvc,
    search: Annotated[str | None, Query(max_length=100)] = None,
    membership_only: Annotated[
        bool,
        Query(description="true 时仅返回当前用户 membership（含 personal），平台 admin 亦同"),
    ] = False,
    include_anonymous_personal: Annotated[
        bool,
        Query(
            description="平台 admin 全站列表是否包含匿名用户的 personal team（默认 false，即排除）"
        ),
    ] = False,
) -> list[TeamResponse]:
    user_uuid = uuid.UUID(current_user.id)
    is_platform_admin = current_user.role == Role.ADMIN.value
    items_data = await svc.list_teams_for_gateway(
        user_uuid,
        is_platform_admin=is_platform_admin and not membership_only,
        search=search,
        exclude_anonymous_personal=not include_anonymous_personal,
    )
    out: list[TeamResponse] = []
    for t, role in items_data:
        resp = TeamResponse.model_validate(t)
        resp.team_role = role
        out.append(resp)
    if is_platform_admin and not membership_only:
        await _enrich_foreign_personal_team_owners(out, user_service, viewer_id=user_uuid)
    return out


async def _enrich_foreign_personal_team_owners(
    teams: list[TeamResponse],
    user_service: UserUseCase,
    *,
    viewer_id: uuid.UUID,
) -> None:
    """他人 personal team 补充 owner 邮箱/姓名，避免 UI 全部显示「个人工作区」。"""
    owner_ids = [
        team.owner_user_id
        for team in teams
        if team.kind == "personal" and team.owner_user_id != viewer_id
    ]
    if not owner_ids:
        return
    summaries = await user_service.list_summary_views_by_ids(owner_ids)
    for team in teams:
        if team.kind != "personal" or team.owner_user_id == viewer_id:
            continue
        summary = summaries.get(team.owner_user_id)
        if summary is None:
            continue
        team.owner_email = summary.email
        team.owner_name = summary.name


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    current_user: RequiredAuthUser,
    svc: TeamSvc,
) -> TeamResponse:
    team = await svc.create_team(
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
    updated = await svc.update_team(
        team_id,
        name=body.name,
        settings=body.settings,
        actor_team_role=team.team_role,
    )
    if updated is None:
        raise NotFoundError("Team")
    return TeamResponse.model_validate(updated)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    team: RequiredTeamOwner,
    svc: TeamSvc,
) -> None:
    record = await svc.get_team(team_id)
    if record is None:
        raise NotFoundError("Team")
    if record.kind == "personal":
        raise ValidationError("Cannot delete personal team")
    try:
        await svc.delete_shared_team(team_id)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: uuid.UUID,
    team: RequiredTeamMember,
    svc: TeamSvc,
    user_service: UserSvc,
) -> list[TeamMemberResponse]:
    members = await svc.list_team_members(team_id)
    enriched = await enrich_team_members(members, user_service)
    return _to_member_responses(enriched)


@router.get(
    "/teams/{team_id}/members/candidates",
    response_model=TeamInviteCandidateListResponse,
)
async def list_team_invite_candidates(
    team_id: uuid.UUID,
    _team: RequiredTeamAdmin,
    current_user: RequiredAuthUser,
    page: PageDep,
    invite_reads: InviteReads,
    svc: TeamSvc,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> TeamInviteCandidateListResponse:
    """分页列出可邀请用户（排除已在团队内的成员；范围见 team.settings.invite_candidate_scope）。"""
    record = await svc.get_team(team_id)
    if record is None:
        raise NotFoundError("Team")
    result = await invite_reads.list_candidates_page(
        page,
        team_id=team_id,
        actor_user_id=uuid.UUID(current_user.id),
        team_settings=record.settings,
        search=search,
    )
    return to_invite_candidate_list_response(result)


@router.get("/teams/{team_id}/members/lookup", response_model=TeamMemberLookupResponse)
async def lookup_user_for_team_invite(
    team_id: uuid.UUID,
    team: RequiredTeamAdmin,
    email: Annotated[str, Query(min_length=3, max_length=320)],
    user_service: UserSvc,
) -> TeamMemberLookupResponse:
    """按邮箱查找已注册用户（团队 admin+，用于添加成员）。"""
    _ = team_id
    summary = await user_service.lookup_user_by_email(email)
    return TeamMemberLookupResponse(
        id=uuid.UUID(summary.id),
        email=summary.email,
        name=summary.name,
    )


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    team: RequiredTeamAdmin,
    svc: TeamSvc,
    user_service: UserSvc,
) -> TeamMemberResponse:
    try:
        member = await svc.add_member(team_id, body.user_id, body.role)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    enriched = await enrich_team_members([member], user_service)
    return _to_member_responses(enriched)[0]


@router.delete(
    "/teams/{team_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_self_from_team(
    team_id: uuid.UUID,
    team: RequiredTeamMember,
    current_user: RequiredAuthUser,
    svc: TeamSvc,
) -> None:
    """当前用户退出所在团队（personal 的 owner 不可退出，与 remove_member 规则一致）。"""
    try:
        await svc.remove_member(team_id, uuid.UUID(current_user.id))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.delete("/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    team: RequiredTeamAdmin,
    svc: TeamSvc,
) -> None:
    try:
        await svc.remove_member(team_id, user_id)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
