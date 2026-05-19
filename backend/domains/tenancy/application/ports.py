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


__all__ = ["TeamResolutionPort", "TeamSnapshot"]
