"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.management.access_assertions import (
    GatewayManagementAccessAssertions,
)
from domains.gateway.application.model_reference_prune import (
    prune_gateway_model_name_references,
)
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.policies.budget_scope_policy import (
    BudgetTeamContext,
    budget_target_allowed,
)
from domains.gateway.domain.types import BudgetScope
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_plan import ProviderPlan
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.provider_plan_repository import (
    ProviderPlanRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.tenancy.application.team_service import TeamService
from utils.logging import get_logger

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession



logger = get_logger(__name__)



class GatewayManagementWriteBaseMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._system_creds = SystemProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._alerts = GatewayAlertRepository(session)
        self._provider_plans = ProviderPlanRepository(session)
        self._entitlement_plans = EntitlementPlanRepository(session)
        self._teams = TeamService(session)
        self._access = GatewayManagementAccessAssertions(
            creds=self._creds,
            vkeys=self._vkeys,
            api_key_grants=ApiKeyUseCase(session),
            entitlement_plans=self._entitlement_plans,
        )

    async def _ensure_personal_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID:
        personal_team = await self._teams.ensure_personal_team(user_id)
        return personal_team.id

    async def _ensure_personal_team_id(self, user_id: uuid.UUID) -> uuid.UUID:
        import warnings

        warnings.warn(
            "_ensure_personal_team_id is deprecated; use _ensure_personal_tenant_id",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self._ensure_personal_tenant_id(user_id)

    async def _assert_user_owns_credential(self, user_id: uuid.UUID, credential_id: uuid.UUID) -> None:
        cred = await self._creds.get(credential_id)
        if cred is None or cred.scope != 'user' or cred.scope_id != user_id:
            raise CredentialNotFoundError(str(credential_id))

    async def _cascade_delete_models_for_credential(self, credential_id: uuid.UUID) -> int:
        """删除引用该凭据的全部注册模型（租户 + 系统），并修剪 vkey / 路由中的模型名。"""
        tenant_models = await self._models.list_by_credential_id(credential_id)
        system_models = await self._models.list_system(
            credential_id=credential_id,
            only_enabled=False,
        )
        if not tenant_models and not system_models:
            return 0
        model_names = frozenset(m.name for m in (*tenant_models, *system_models))
        for model in tenant_models:
            await self._models.delete(model.id)
        for model in system_models:
            await self._models.delete_system(model.id)
        await prune_gateway_model_name_references(self._session, model_names)
        return len(tenant_models) + len(system_models)

    async def _assert_credential_in_team(self, credential_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        """与 ``list_credentials_for_team`` 可见集合一致：team-scope 凭据 + 平台管理员可见 system。"""
        row = await self._creds.get_bindable_for_team_gateway_model(credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        if row is None:
            raise CredentialNotFoundError(str(credential_id))

    async def _assert_provider_plan_in_credential(self, plan_id: uuid.UUID, *, credential_id: uuid.UUID) -> ProviderPlan:
        plan = await self._provider_plans.get(plan_id)
        if plan is None or plan.credential_id != credential_id:
            raise ManagementEntityNotFoundError('provider_plan', str(plan_id))
        return plan

    async def _assert_vkey_in_team(self, vkey_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        record = await self._vkeys.get(vkey_id)
        if record is None:
            raise VirtualKeyNotFoundError(str(vkey_id))
        if not is_platform_admin and record.tenant_id != tenant_id:
            raise VirtualKeyNotFoundError(str(vkey_id))

    async def _assert_apikey_grant_in_team(self, grant_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        await self._access.assert_apikey_grant_in_team(
            grant_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

    async def _assert_entitlement_plan_in_team(self, plan_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> EntitlementPlan:
        plan = await self._entitlement_plans.get(plan_id)
        if plan is None:
            raise ManagementEntityNotFoundError('entitlement_plan', str(plan_id))
        if plan.target_kind == 'vkey':
            await self._assert_vkey_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        elif plan.target_kind == 'apikey_grant':
            await self._assert_apikey_grant_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ManagementEntityNotFoundError('entitlement_plan', str(plan_id))
        return plan

    async def _assert_budget_target_in_team(
        self,
        target_kind: str,
        target_id: uuid.UUID | None,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        member_user_ids: frozenset[uuid.UUID] = frozenset()
        if target_kind == BudgetScope.USER.value:
            members = await self._teams.list_team_members(tenant_id)
            member_user_ids = frozenset(m.user_id for m in members)

        ctx = BudgetTeamContext(
            tenant_id=tenant_id,
            member_user_ids=member_user_ids,
            is_platform_admin=is_platform_admin,
        )
        key_belongs_to_team: bool | None = None
        if target_kind == "key":
            if target_id is None:
                raise ManagementEntityNotFoundError("budget", str(target_id))
            try:
                await self._assert_vkey_in_team(
                    target_id,
                    tenant_id=tenant_id,
                    is_platform_admin=is_platform_admin,
                )
                key_belongs_to_team = True
            except VirtualKeyNotFoundError as exc:
                raise ManagementEntityNotFoundError("budget", str(target_id)) from exc

        if not budget_target_allowed(
            target_kind,
            target_id,
            ctx,
            key_belongs_to_team=key_belongs_to_team,
        ):
            detail = str(target_id) if target_id is not None else target_kind
            raise ManagementEntityNotFoundError("budget", detail)

    async def _assert_budget_in_team(
        self,
        budget_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        budget = await self._budgets.get(budget_id)
        if budget is None:
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        await self._assert_budget_target_in_team(
            budget.target_kind,
            budget.target_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

    async def reload_litellm_router(self) -> None:
        from domains.gateway.infrastructure.router_singleton import reload_router

        try:
            await reload_router(self._session)
        except Exception:
            logger.exception("LiteLLM Router reload failed")
