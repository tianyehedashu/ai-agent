"""团队相关请求/响应模型（与历史 ``gateway`` 契约字段对齐）。"""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from libs.api.pagination import PaginatedListResponse

JsonObject = dict[str, object]


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = None
    settings: JsonObject | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    settings: JsonObject | None = None


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    owner_user_id: uuid.UUID
    settings: JsonObject | None = None
    is_active: bool = True
    created_at: datetime
    team_role: str | None = None
    """平台 admin 列全站团队时，他人 personal team 的归属用户（用于 UI 区分）。"""
    owner_email: str | None = None
    owner_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamMemberAdd(BaseModel):
    """邀请成员仅允许 ``admin`` / ``member``；``owner`` 由 ``Team.owner_user_id`` 唯一表示。"""

    user_id: uuid.UUID
    role: str = Field(default="member", pattern="^(admin|member)$")


class TeamMemberResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    user_email: str | None = None
    user_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamMemberLookupResponse(BaseModel):
    """按邮箱查找用户（团队 admin 添加成员前，不暴露平台 role）。"""

    id: uuid.UUID
    email: str
    name: str | None = None


class TeamInviteCandidateResponse(BaseModel):
    """可邀请用户摘要（分页列表项，与 lookup 字段一致）。"""

    id: uuid.UUID
    email: str
    name: str | None = None


class TeamInviteCandidateListResponse(
    PaginatedListResponse[TeamInviteCandidateResponse]
):
    """可邀请用户分页列表。"""


__all__ = [
    "TeamCreate",
    "TeamInviteCandidateListResponse",
    "TeamInviteCandidateResponse",
    "TeamMemberAdd",
    "TeamMemberLookupResponse",
    "TeamMemberResponse",
    "TeamResponse",
    "TeamUpdate",
]
