"""Gateway 管理面实体归属断言（从读服务拆出，控制 facade 公开方法数量）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    VirtualKeyNotFoundError,
)
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )
    from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
        EntitlementPlanRepository,
    )
    from domains.gateway.infrastructure.repositories.virtual_key_repository import (
        VirtualKeyRepository,
    )
    from domains.identity.application.ports import ApiKeyGatewayGrantQueryPort


class GatewayManagementAccessAssertions:
    """管理 API 写/读路径共用的团队内实体存在性校验。"""

    def __init__(
        self,
        *,
        creds: ProviderCredentialRepository,
        vkeys: VirtualKeyRepository,
        api_key_grants: ApiKeyGatewayGrantQueryPort,
        entitlement_plans: EntitlementPlanRepository,
    ) -> None:
        self._creds = creds
        self._vkeys = vkeys
        self._api_key_grants = api_key_grants
        self._entitlement_plans = entitlement_plans

    async def assert_credential_in_team(
        self,
        credential_id: UUID,
        *,
        tenant_id: UUID,
        is_platform_admin: bool,
    ) -> ProviderCredential:
        row = await self._creds.get_bindable_for_team_gateway_model(
            credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        if row is None:
            raise CredentialNotFoundError(str(credential_id))
        return row

    async def assert_vkey_in_team(
        self,
        vkey_id: UUID,
        *,
        tenant_id: UUID,
        is_platform_admin: bool,
    ) -> None:
        record = await self._vkeys.get(vkey_id)
        if record is None:
            raise VirtualKeyNotFoundError(str(vkey_id))
        if not is_platform_admin and record.tenant_id != tenant_id:
            raise VirtualKeyNotFoundError(str(vkey_id))

    async def assert_apikey_grant_in_team(
        self,
        grant_id: UUID,
        *,
        tenant_id: UUID,
        is_platform_admin: bool,
    ) -> None:
        from libs.exceptions import NotFoundError

        try:
            await self._api_key_grants.assert_gateway_grant_in_team(
                grant_id,
                team_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )
        except NotFoundError as exc:
            raise ManagementEntityNotFoundError("apikey_grant", str(grant_id)) from exc

    async def assert_entitlement_plan_in_team(
        self,
        plan_id: UUID,
        *,
        tenant_id: UUID,
        is_platform_admin: bool,
    ) -> EntitlementPlan:
        plan = await self._entitlement_plans.get(plan_id)
        if plan is None:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        if plan.target_kind == "vkey":
            await self.assert_vkey_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        elif plan.target_kind == "apikey_grant":
            await self.assert_apikey_grant_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        return plan


__all__ = ["GatewayManagementAccessAssertions"]
