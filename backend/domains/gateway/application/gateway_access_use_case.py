"""Gateway 鉴权与团队上下文（应用层 UseCase）

读多写少：团队解析、虚拟 Key 校验为查询语义；`touch` 为单次写操作、与校验同属一条鉴权用例，
故合并为本 UseCase，避免为单行写入单独维护 Command 类型（与 CQRS 不冲突，见域文档说明）。

成员角色仅经 ``MembershipPort``，不直接使用 ``TeamMemberRepository``。

平台 ``sk-*`` + ``gateway:proxy`` 的验签与团队 grant 解析亦收拢于此，Presentation 仅依赖本用例。
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.platform_api_key_proxy_dto import (
    PlatformApiKeyGatewayProxyAuth,
)
from domains.gateway.domain.errors import (
    ApiKeyGatewayGrantDeniedError,
    ApiKeyGatewayGrantRequiredError,
    GatewayTeamHeaderInvalidError,
    GatewayTeamHeaderRequiredError,
    NoPersonalTeamForProxyError,
    PlatformApiKeyInvalidError,
    PlatformApiKeyMissingGatewayProxyScopeError,
    TeamNotFoundError,
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
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.identity.domain.api_key_types import (
    ApiKeyEntity,
    ApiKeyGatewayGrantEntity,
    ApiKeyScope,
)
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.iam.tenancy import MembershipPort, TenantId

if TYPE_CHECKING:
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

    async def authenticate_platform_sk_for_gateway_proxy(
        self,
        plain: str,
        x_team_id: str | None,
    ) -> PlatformApiKeyGatewayProxyAuth:
        """校验平台 ``sk-*``、校验 ``gateway:proxy`` scope，并按 grant 解析计费团队。"""
        keys = ApiKeyUseCase(self._session)
        entity = await keys.verify_api_key(plain)
        if entity is None or not entity.is_valid:
            raise PlatformApiKeyInvalidError()
        if not entity.can_access(ApiKeyScope.GATEWAY_PROXY):
            raise PlatformApiKeyMissingGatewayProxyScopeError()

        team, team_role, grant = await self._resolve_team_grant_for_platform_api_key(
            entity, x_team_id
        )
        return PlatformApiKeyGatewayProxyAuth(
            user_id=entity.user_id,
            api_key_id=entity.id,
            team_id=team.id,
            team_role=team_role,
            grant_id=grant.id,
            allowed_models=tuple(grant.allowed_models),
            allowed_capabilities=tuple(grant.allowed_capabilities or ()),
            rpm_limit=grant.rpm_limit,
            tpm_limit=grant.tpm_limit,
            store_full_messages=grant.store_full_messages,
            guardrail_enabled=grant.guardrail_enabled,
        )

    async def _resolve_team_grant_for_platform_api_key(
        self,
        api_key: ApiKeyEntity,
        x_team_id: str | None,
    ) -> tuple[Team, str, ApiKeyGatewayGrantEntity]:
        """解析平台 API Key 的 Gateway 团队授权。

        ``X-Team-Id`` 只用于选择该 API Key 已持有的 grant；若未授权则拒绝，
        不再回退为“用户所属团队皆可用”。
        """
        grants = tuple(g for g in api_key.gateway_grants if g.is_active)
        if not grants:
            raise ApiKeyGatewayGrantRequiredError()

        target_team_id: uuid.UUID | None = None
        if x_team_id:
            try:
                target_team_id = uuid.UUID(x_team_id)
            except ValueError as exc:
                raise GatewayTeamHeaderInvalidError(x_team_id) from exc
        else:
            personal = await self._teams.get_personal(api_key.user_id)
            if personal is not None:
                personal_grant = next((g for g in grants if g.team_id == personal.id), None)
                if personal_grant is not None:
                    target_team_id = personal.id
            if target_team_id is None:
                if len(grants) == 1:
                    target_team_id = grants[0].team_id
                else:
                    raise GatewayTeamHeaderRequiredError()

        grant = next((g for g in grants if g.team_id == target_team_id), None)
        if grant is None:
            raise ApiKeyGatewayGrantDeniedError(str(target_team_id))

        team = await self._teams.get(target_team_id)
        if team is None or not team.is_active:
            raise TeamNotFoundError(str(target_team_id))

        role = await self._membership.member_role(
            self._session, tenant_id=TenantId(team.id), user_id=api_key.user_id
        )
        if role is None:
            raise TeamPermissionDeniedError(str(team.id))
        return team, role, grant


__all__ = ["GatewayAccessUseCase"]
