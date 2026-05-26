"""Tenancy 读侧：批量解析用户 role（infrastructure 防腐层，隔离 identity ORM）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class IdentityUserRoleLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def roles_by_user_ids(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        from domains.identity.infrastructure.repositories import SQLAlchemyUserRepository

        unique_ids = list(dict.fromkeys(user_ids))
        users = await SQLAlchemyUserRepository(self._session).list_by_ids(unique_ids)
        return {user.id: user.role for user in users}


__all__ = ["IdentityUserRoleLookup"]
