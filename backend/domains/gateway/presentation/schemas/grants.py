"""grants.py — 跨团队 vkey 授权 schema"""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class VirtualKeyTeamGrantResponse(BaseModel):
    """单条 active grant 响应"""

    id: uuid.UUID
    vkey_id: uuid.UUID
    tenant_id: uuid.UUID
    is_self: bool
    created_at: datetime
    revoked_at: datetime | None = None
    granted_team_name: str | None = None
    granted_team_slug: str | None = None
    model_count: int = 0
    registered_model_names: list[str] = Field(default_factory=list)


class VirtualKeyGrantBatchRequest(BaseModel):
    """批量授权请求"""

    tenant_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class GrantableTeamResponse(BaseModel):
    """可授权 team"""

    team_id: uuid.UUID
    name: str
    slug: str
    model_count: int = 0


__all__ = [
    "GrantableTeamResponse",
    "VirtualKeyGrantBatchRequest",
    "VirtualKeyTeamGrantResponse",
]
