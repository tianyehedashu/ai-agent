"""Gateway 鉴权与团队上下文（应用层 UseCase）

读多写少：团队解析、虚拟 Key 校验为查询语义；`touch` 为单次写操作、与校验同属一条鉴权用例，
故合并为本 UseCase，避免为单行写入单独维护 Command 类型（与 CQRS 不冲突，见域文档说明）。

成员角色仅经 ``MembershipPort``，不直接使用 ``TeamMemberRepository``。
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import (
    NoPersonalTeamForProxyError,
    TeamPermissionDeniedError,
    VirtualKeyInvalidError,
)
from domains.gateway.domain.virtual_key_service import (
    extract_key_id,
    hash_vkey,
    verify_vkey,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.iam.tenancy import MembershipPort, TenantId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
    from domains.tenancy.infrastructure.models.team import Team


class GatewayAccessUseCase:
    """Bearer 虚拟 Key、API Key 代理、管理面团队解析及 vkey 使用回写"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        membership: MembershipPort | None = None,
    ) -> None:
        self._session = session
        self._vkeys = VirtualKeyRepository(session)
        self._teams = TeamRepository(session)
        self._membership = membership or TenancyMembershipAdapter()

    async def validate_bearer_virtual_key(self, plain: str) -> GatewayVirtualKey:
        record = await self._vkeys.get_by_hash(hash_vkey(plain))
        if record is None or not record.is_valid:
            raise VirtualKeyInvalidError("Invalid or revoked virtual key")
        expected_key_id = extract_key_id(plain)
        if expected_key_id != record.key_id or not verify_vkey(plain, record.key_hash):
            raise VirtualKeyInvalidError("Invalid virtual key")
        return record

    async def record_virtual_key_usage(self, vkey_id: uuid.UUID) -> None:
        await self._vkeys.touch_used(vkey_id)

    async def team_role_for_virtual_key_creator(
        self, team_id: uuid.UUID, created_by_user_id: uuid.UUID | None
    ) -> str:
        if created_by_user_id is None:
            return "member"
        role = await self._membership.member_role(
            self._session,
            tenant_id=TenantId(team_id),
            user_id=created_by_user_id,
        )
        return role if role is not None else "member"

    async def resolve_team_for_gateway_proxy(
        self, user_id: uuid.UUID, x_team_id: str | None
    ) -> tuple[Team, str]:
        team: Team | None = None
        if x_team_id:
            with suppress(ValueError):
                team = await self._teams.get(uuid.UUID(x_team_id))
        if team is None:
            team = await self._teams.get_personal(user_id)
        if team is None:
            raise NoPersonalTeamForProxyError()
        role = await self._membership.member_role(
            self._session, tenant_id=TenantId(team.id), user_id=user_id
        )
        if role is None:
            raise TeamPermissionDeniedError(str(team.id))
        return team, role


__all__ = ["GatewayAccessUseCase"]
