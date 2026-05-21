"""Session 访问策略：会话归属个人工作区（personal tenant）。"""

from __future__ import annotations

from typing import Protocol
import uuid


class SessionTenantLike(Protocol):
    """仅需 tenant_id 的会话视图。"""

    tenant_id: uuid.UUID


def is_session_in_personal_tenant(
    session: SessionTenantLike,
    personal_tenant_id: uuid.UUID,
) -> bool:
    """会话是否落在指定用户的 personal team tenant。"""
    return session.tenant_id == personal_tenant_id


def can_access_personal_session(
    session: SessionTenantLike,
    *,
    personal_tenant_id: uuid.UUID,
    is_platform_admin: bool,
) -> bool:
    """主体是否可访问该 personal 会话（平台 admin 旁路）。"""
    if is_platform_admin:
        return True
    return is_session_in_personal_tenant(session, personal_tenant_id)


__all__ = [
    "SessionTenantLike",
    "can_access_personal_session",
    "is_session_in_personal_tenant",
]
