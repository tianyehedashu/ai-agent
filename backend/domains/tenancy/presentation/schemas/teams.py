"""团队相关请求/响应模型（与历史 ``gateway`` 契约字段对齐）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = None
    settings: dict[str, Any] | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    settings: dict[str, Any] | None = None


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    owner_user_id: uuid.UUID
    settings: dict[str, Any] | None = None
    is_active: bool = True
    created_at: datetime
    team_role: str | None = None

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

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "TeamCreate",
    "TeamMemberAdd",
    "TeamMemberResponse",
    "TeamResponse",
    "TeamUpdate",
]
