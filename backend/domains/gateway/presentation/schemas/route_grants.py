"""route_grants.py — 路由跨团队共享授权 schema"""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class RouteGrantResponse(BaseModel):
    """路由 owner 视角：单条 active 共享授权"""

    id: uuid.UUID
    route_id: uuid.UUID
    tenant_id: uuid.UUID
    exposed_alias: str
    virtual_model: str | None = None
    granted_team_name: str | None = None
    granted_team_slug: str | None = None
    created_at: datetime


class RouteGrantCreateRequest(BaseModel):
    """发布路由到团队"""

    target_tenant_id: uuid.UUID
    exposed_alias: str | None = Field(default=None, max_length=200)


class RouteGrantAliasUpdateRequest(BaseModel):
    """修改暴露别名"""

    exposed_alias: str = Field(..., min_length=1, max_length=200)


class SharedRouteResponse(BaseModel):
    """团队侧视角：共享进本团队的路由（只读 + 可移除）"""

    grant_id: uuid.UUID
    route_id: uuid.UUID
    tenant_id: uuid.UUID
    exposed_alias: str
    virtual_model: str | None = None
    owner_user_id: uuid.UUID | None = None
    owner_display: str | None = None
    created_at: datetime


class RouteGrantableTeamResponse(BaseModel):
    """可作为共享目标的团队"""

    team_id: uuid.UUID
    name: str
    slug: str


__all__ = [
    "RouteGrantAliasUpdateRequest",
    "RouteGrantCreateRequest",
    "RouteGrantResponse",
    "RouteGrantableTeamResponse",
    "SharedRouteResponse",
]
