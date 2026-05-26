"""Tenancy application ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import uuid


@dataclass(frozen=True)
class TeamSnapshot:
    """团队只读快照（跨域传递，不含 ORM）。"""

    id: uuid.UUID
    is_active: bool
    kind: str
    owner_user_id: uuid.UUID | None


@dataclass(frozen=True)
class GatewayTeamMembershipSnapshot:
    """Gateway 管理面团队 membership（跨域读侧，不含 ORM）。"""

    team_id: uuid.UUID
    kind: str
    role: str


class TeamResolutionPort(Protocol):
    """团队解析端口（供 Gateway / Identity 等消费）。"""

    async def get_team(self, team_id: uuid.UUID) -> TeamSnapshot | None:
        """按 ID 获取团队快照"""
        ...

    async def get_personal_team(self, user_id: uuid.UUID) -> TeamSnapshot | None:
        """获取用户 personal team"""
        ...

    async def resolve_team_for_gateway_proxy(
        self,
        user_id: uuid.UUID,
        x_team_id: str | None,
    ) -> tuple[TeamSnapshot, str]:
        """解析 /v1 代理计费团队及成员角色"""
        ...


class GatewayTeamListingPort(Protocol):
    """Gateway 管理面团队列表（membership + 角色，供凭据/模型读侧聚合）。"""

    async def list_gateway_team_memberships(
        self,
        user_id: uuid.UUID,
        *,
        is_platform_admin: bool,
        search: str | None = None,
        exclude_anonymous_personal: bool = True,
    ) -> list[GatewayTeamMembershipSnapshot]:
        """普通用户仅 membership；平台 admin 可见活跃团队（默认不含匿名 personal）。"""
        ...


__all__ = [
    "GatewayTeamListingPort",
    "GatewayTeamMembershipSnapshot",
    "TeamResolutionPort",
    "TeamSnapshot",
]
