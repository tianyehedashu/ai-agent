"""批量解析用户平台 role（identity 域内实现，供 tenancy 等消费方经端口调用）。"""

from collections.abc import Sequence
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.ports import UserPlatformRoleLookupPort
from domains.identity.infrastructure.repositories import SQLAlchemyUserRepository


class UserPlatformRoleLookupAdapter(UserPlatformRoleLookupPort):
    def __init__(self, session: AsyncSession) -> None:
        self._users = SQLAlchemyUserRepository(session)

    async def roles_by_user_ids(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        unique_ids = list(dict.fromkeys(user_ids))
        users = await self._users.list_by_ids(unique_ids)
        return {user.id: user.role for user in users}


__all__ = ["UserPlatformRoleLookupAdapter"]
