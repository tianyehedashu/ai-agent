"""VirtualKeyGrantLifecyclePort 默认实现（gateway 域内，供 tenancy 生命周期 hook 注入）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.vkey.management.virtual_key_team_grant_writes import (
    revoke_grants_for_team_deleted,
    revoke_grants_for_user_team_membership,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class VirtualKeyGrantLifecycleAdapter:
    """成员变更 / 团队删除时同步撤销 vkey 跨团队授权。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def revoke_for_membership_lost(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> int:
        return await revoke_grants_for_user_team_membership(
            self._session,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    async def revoke_for_team_deleted(self, *, tenant_id: uuid.UUID) -> int:
        return await revoke_grants_for_team_deleted(self._session, tenant_id=tenant_id)


__all__ = ["VirtualKeyGrantLifecycleAdapter"]
