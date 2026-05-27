"""Tenancy 读侧：用户 platform role（委托 identity ``UserPlatformRoleLookupPort``）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.ports import UserPlatformRoleLookupPort
from domains.identity.infrastructure.user_platform_role_lookup import (
    UserPlatformRoleLookupAdapter,
)


def user_platform_role_lookup_for_session(
    session: AsyncSession,
) -> UserPlatformRoleLookupPort:
    """为 tenancy 装配 identity 用户 role 查询端口。"""
    return UserPlatformRoleLookupAdapter(session)


__all__ = [
    "UserPlatformRoleLookupPort",
    "user_platform_role_lookup_for_session",
]
