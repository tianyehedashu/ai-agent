"""Gateway 管理面只读应用服务（CQRS 读侧的工程分包；对外语义见架构文档术语表）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from domains.gateway.application.entitlement_model_status import is_connectivity_requestable
from domains.gateway.application.gateway_model_listing import (
    GatewayRegistryModelRow,
    list_callable_system_model_names,
    list_merged_models_for_tenant,
)
from domains.gateway.application.management.access_assertions import (
    GatewayManagementAccessAssertions,
)
from domains.gateway.application.management.alert_read_model import (
    AlertRuleSummary,
    alert_rule_from_orm,
)
from domains.gateway.application.management.credential_read_mappers import (
    credential_from_orm,
    system_credential_from_orm,
)
from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.application.management.plan_read_mappers import (
    entitlement_plan_from_orm,
    provider_plan_from_orm,
)
from domains.gateway.application.management.plan_read_models import (
    EntitlementPlanReadModel,
    ProviderPlanReadModel,
)
from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleListFilters,
    QuotaRuleReadModel,
)
from domains.gateway.application.management.usage_log_reads import GatewayUsageLogReadMixin
from domains.gateway.application.management.usage_reads import (
    EntitlementUsageReadModel,
    GatewayPlanUsageReadService,
    MarginSummaryReadModel,
    ProviderPlanCostReadModel,
)
from domains.gateway.application.management.virtual_key_read_mappers import virtual_key_from_orm
from domains.gateway.application.management.virtual_key_read_model import VirtualKeyReadModel
from domains.gateway.application.model_list_credential_assertions import (
    assert_personal_model_list_credential_filter,
    assert_team_model_list_credential_filter,
)
from domains.gateway.application.model_list_pipeline import (
    ModelListIdsResult,
    ModelListPageResult,
    ModelListQuery,
    list_gateway_model_ids,
    list_gateway_models_page,
    list_personal_models_page,
)
from domains.gateway.application.system_visibility_filter import (
    filter_visible_system_provider_credentials,
    load_system_credentials_by_ids,
)
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.margin_read_model import MarginGroupBy
from domains.gateway.domain.policies.budget_scope_policy import (
    filter_budget_rows,
    normalize_budget_list_filters,
    plan_admin_budget_fetch,
)
from domains.gateway.domain.policies.model_registry_scope import (
    exclude_user_scope_credentials_for_registry,
)
from domains.gateway.domain.team_credential_access import (
    assert_team_credential_readable_by_actor,
    filter_team_credentials_visible_to_actor,
)
from domains.gateway.domain.types import CredentialScope, credential_api_scope
from domains.gateway.domain.virtual_key_access import (
    assert_virtual_key_accessible_by_actor,
    filter_virtual_keys_visible_to_actor,
)
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayModel,
    SystemProviderCredential,
)
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
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.identity.application.ports import ApiKeyGatewayGrantQueryPort, UserSummaryQueryPort
from domains.identity.application.user_use_case import UserUseCase
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from libs.api.pagination import slice_page
from libs.iam.tenancy import MembershipPort

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.management.playground_credential_reads import (
        PlaygroundCredentialSummaryItem,
    )


class GatewayManagementReadService(GatewayUsageLogReadMixin):
    """管理 API 只读用例，经仓储访问数据"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        membership: MembershipPort | None = None,
        api_key_grants: ApiKeyGatewayGrantQueryPort | None = None,
        user_summaries: UserSummaryQueryPort | None = None,
    ) -> None:
        self._session = session
        self._membership = membership or TenancyMembershipAdapter()
        self._api_key_grants: ApiKeyGatewayGrantQueryPort = api_key_grants or ApiKeyUseCase(session)
        self._user_summaries: UserSummaryQueryPort = user_summaries or UserUseCase(session)
        self._teams = TeamService(session, membership=self._membership)
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._system_creds = SystemProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._logs = RequestLogRepository(session)
        self._alerts = GatewayAlertRepository(session)
        self._provider_plans = ProviderPlanRepository(session)
        self._entitlement_plans = EntitlementPlanRepository(session)
        self._plan_usage = GatewayPlanUsageReadService(session)
        self.access = GatewayManagementAccessAssertions(
            creds=self._creds,
            vkeys=self._vkeys,
            api_key_grants=self._api_key_grants,
            entitlement_plans=self._entitlement_plans,
        )

    async def list_virtual_keys_for_team(
        self,
        team_id: UUID,
        *,
        actor_user_id: UUID | None = None,
        team_role: str = "owner",
        is_platform_admin: bool = False,
    ) -> list[VirtualKeyReadModel]:
        keys = await self._vkeys.list_for_tenant(
            team_id, include_system=False, include_inactive=False
        )
        filtered = filter_virtual_keys_visible_to_actor(
            keys,
            actor_user_id=actor_user_id,
        )
        return [virtual_key_from_orm(k) for k in filtered]

    async def get_virtual_key_for_team_member(
        self,
        key_id: UUID,
        *,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> VirtualKeyReadModel:
        """按 revoke/reveal 同款权限取一条 active vkey。"""
        record = await self._vkeys.get(key_id)
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=str(key_id),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            require_active=True,
        )
        if record is None:
            raise VirtualKeyNotFoundError(str(key_id))
        return virtual_key_from_orm(record)

    async def list_credentials_for_team(
        self,
        team_id: UUID,
        *,
        include_system: bool,
        encryption_key: str | None = None,
    ) -> list[CredentialReadModel]:
        """团队 workspace 列表：租户内全部 team-scope 行；分级在 presentation 组装。"""
        rows = await self._creds.list_for_tenant(team_id)
        out = [credential_from_orm(c, encryption_key=encryption_key) for c in rows]
        if include_system:
            system_rows = await self._system_creds.list_all()
            out.extend(
                system_credential_from_orm(c, encryption_key=encryption_key) for c in system_rows
            )
        return out

    async def assert_credential_in_managed_tenants(
        self,
        credential_id: UUID | None,
        *,
        allowed_tenant_ids: list[UUID],
    ) -> None:
        if credential_id is None:
            return
        await self.access.assert_credential_in_managed_tenants(
            credential_id,
            allowed_tenant_ids=allowed_tenant_ids,
        )

    async def list_credential_summaries_for_team(
        self,
        team_id: UUID,
        *,
        user_id: UUID | None = None,
        team_role: str = "member",
        is_platform_admin: bool = False,
    ) -> list[CredentialReadModel]:
        """团队内全部 team 凭据摘要 + ACL 过滤后的 system（无密钥；模型绑定下拉用）。"""
        rows = await self._creds.list_for_tenant(team_id)
        out = [credential_from_orm(c) for c in rows]
        system_rows = await self._system_creds.list_all()
        visible_system = await filter_visible_system_provider_credentials(
            self._session,
            system_rows,
            tenant_id=team_id,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
        )
        out.extend(system_credential_from_orm(c) for c in visible_system)
        return out

    async def get_managed_credential_for_team(
        self,
        credential_id: UUID,
        *,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> CredentialReadModel:
        """reveal/写路径：仅创建者或 legacy admin+ 可读（与 workspace 全量列表分离）。"""
        row = await self._creds.get_bindable_for_team_gateway_model(
            credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        if row is None:
            raise CredentialNotFoundError(str(credential_id))
        from domains.gateway.infrastructure.models.provider_credential import (
            ProviderCredential,
        )
        from domains.gateway.infrastructure.models.system_gateway import (
            SystemProviderCredential,
        )

        if isinstance(row, ProviderCredential):
            assert_team_credential_readable_by_actor(
                row,
                credential_id=credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
            return credential_from_orm(row)
        if isinstance(row, SystemProviderCredential):
            return system_credential_from_orm(row)
        raise CredentialNotFoundError(str(credential_id))

    async def map_team_credentials_display_by_id(
        self,
        credential_ids: set[UUID],
    ) -> dict[UUID, ProviderCredential]:
        """模型列表/详情 enrich：凭据名、创建者等展示字段（不做 reveal 过滤；响应不含密钥）。"""
        if not credential_ids:
            return {}
        rows = await self._creds.list_by_ids(list(credential_ids))
        return {row.id: row for row in rows}

    async def map_team_credentials_visible_display_by_id(
        self,
        credential_ids: set[UUID],
        *,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> dict[UUID, ProviderCredential]:
        """绑定/摘要专用：仅 actor reveal 可读集合（workspace 列表用 ``map_team_credentials_display_by_id``）。"""
        if not credential_ids or actor_user_id is None:
            return {}
        rows = await self._creds.list_by_ids(list(credential_ids))
        visible = filter_team_credentials_visible_to_actor(
            [r for r in rows if r.tenant_id == tenant_id],
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
        return {row.id: row for row in visible}

    async def get_user_credential_for_owner(
        self, credential_id: UUID, user_id: UUID
    ) -> CredentialReadModel:
        """与 ``list_user_credentials`` 可见集合一致：仅当前用户的 user-scope 凭据。"""
        row = await self._creds.get(credential_id)
        if row is None:
            raise CredentialNotFoundError(str(credential_id))
        if row.scope != "user" or row.scope_id != user_id:
            raise CredentialNotFoundError(str(credential_id))
        return credential_from_orm(row)

    async def list_user_credentials(
        self,
        user_id: UUID,
        *,
        encryption_key: str | None = None,
    ) -> list[CredentialReadModel]:
        rows = await self._creds.list_for_user(user_id)
        return [credential_from_orm(c, encryption_key=encryption_key) for c in rows]

    async def list_playground_credential_summaries_for_actor(
        self,
        user_id: UUID,
        *,
        is_platform_admin: bool = False,
    ) -> list[PlaygroundCredentialSummaryItem]:
        """Playground / 调用指南：跨 membership 聚合凭据摘要（含 context_team_id）。"""
        from domains.gateway.application.management.playground_credential_reads import (
            list_playground_credential_summaries_for_actor,
        )

        return await list_playground_credential_summaries_for_actor(
            self._session,
            self,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
        )

    async def list_personal_gateway_models(
        self,
        user_id: UUID,
        *,
        provider: str | None = None,
    ) -> list[GatewayModel]:
        personal_team = await self._teams.ensure_personal_team(user_id)
        return await self._models.list_tenant_owned(
            personal_team.id,
            only_enabled=False,
            provider=provider,
        )

    async def list_personal_gateway_models_page(
        self,
        user_id: UUID,
        query: ModelListQuery,
    ) -> ModelListPageResult:
        await assert_personal_model_list_credential_filter(
            self, query.credential_id, user_id=user_id
        )
        personal_team = await self._teams.ensure_personal_team(user_id)
        return await list_personal_models_page(
            self._session,
            personal_team.id,
            query,
            user_id=user_id,
        )

    async def get_personal_gateway_model(
        self,
        user_id: UUID,
        model_id: UUID,
    ) -> GatewayModel | None:
        personal_team = await self._teams.ensure_personal_team(user_id)
        return await self._models.get_for_tenant(model_id, personal_team.id)

    async def list_gateway_models_page(
        self,
        tenant_id: UUID,
        query: ModelListQuery,
        *,
        registry_scope: Literal["team", "system", "callable", "requestable"] = "team",
        only_enabled: bool = False,
        user_id: UUID | None = None,
        team_role: str = "member",
        is_platform_admin: bool = False,
    ) -> ModelListPageResult:
        if user_id is not None:
            await assert_team_model_list_credential_filter(
                self,
                query.credential_id,
                tenant_id=tenant_id,
                actor_user_id=user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
        return await list_gateway_models_page(
            self._session,
            tenant_id,
            query,
            registry_scope=registry_scope,
            only_enabled=only_enabled,
            user_id=user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )

    async def list_gateway_model_ids(
        self,
        tenant_id: UUID,
        query: ModelListQuery,
        *,
        registry_scope: Literal["team", "system", "callable", "requestable"] = "team",
        only_enabled: bool = False,
        user_id: UUID | None = None,
        team_role: str = "member",
        is_platform_admin: bool = False,
    ) -> ModelListIdsResult:
        if user_id is not None:
            await assert_team_model_list_credential_filter(
                self,
                query.credential_id,
                tenant_id=tenant_id,
                actor_user_id=user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
        return await list_gateway_model_ids(
            self._session,
            tenant_id,
            query,
            registry_scope=registry_scope,
            only_enabled=only_enabled,
            user_id=user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )

    async def get_gateway_registry_model(
        self,
        model_id: UUID,
        tenant_id: UUID,
        *,
        is_platform_admin: bool,
    ) -> GatewayRegistryModelRow | None:
        row = await self._models.get_for_tenant(model_id, tenant_id)
        if row is not None:
            return row
        if is_platform_admin:
            return await self._models.get_system(model_id)
        return None

    async def list_gateway_models(
        self,
        tenant_id: UUID,
        *,
        registry_scope: Literal["team", "system", "callable", "requestable"] = "team",
        only_enabled: bool,
        provider: str | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[GatewayRegistryModelRow]:
        """``team`` / ``system``：注册表行；``callable``：合并列表；``requestable``：可发起代理请求（enabled 且未 failed）。"""
        if registry_scope == "team":
            return await self._models.list_tenant_owned(
                tenant_id,
                only_enabled=only_enabled,
                provider=provider,
                credential_id=credential_id,
                exclude_user_scope_credentials=exclude_user_scope_credentials_for_registry(
                    registry_scope
                ),
            )
        if registry_scope == "system":
            return await self._models.list_system(
                only_enabled=only_enabled,
                provider=provider,
                credential_id=credential_id,
            )
        merged = await list_merged_models_for_tenant(
            self._session,
            tenant_id,
            only_enabled=True if registry_scope == "requestable" else only_enabled,
            provider=provider,
            credential_id=credential_id,
            user_id=user_id,
            apply_visibility_filter=True,
        )
        if registry_scope == "requestable":
            return [row for row in merged if is_connectivity_requestable(row.last_test_status)]
        return merged

    async def map_system_credentials_by_id(
        self, credential_ids: set[UUID]
    ) -> dict[UUID, SystemProviderCredential]:
        return await load_system_credentials_by_ids(self._session, credential_ids)

    async def personal_team_id_for_user(self, user_id: UUID) -> UUID:
        personal = await self._teams.ensure_personal_team(user_id)
        return personal.id

    async def list_callable_system_model_names(
        self,
        tenant_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> list[str]:
        """callable 合并列表中的平台注册模型名（已应用可见性策略）。"""
        return await list_callable_system_model_names(
            self._session,
            tenant_id,
            user_id=user_id,
        )

    async def list_system_gateway_models(
        self,
        *,
        only_enabled: bool = True,
        provider: str | None = None,
    ) -> list[SystemGatewayModel]:
        return await self._models.list_system(
            only_enabled=only_enabled,
            provider=provider,
        )

    async def list_gateway_routes(self, tenant_id: UUID, *, only_enabled: bool) -> list[Any]:
        return await self._routes.list_for_tenant(tenant_id, only_enabled=only_enabled)

    async def list_budgets_for_tenant_and_user(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        *,
        actor_user_id: UUID | None = None,
    ) -> list[Any]:
        """成员读路径：团队 tenant 预算 + 当前 user 预算 + 可见 vkey 的 key 预算。"""
        budgets: list[Any] = []
        budgets.extend(await self._budgets.list_for_target("tenant", tenant_id))
        if user_id is not None:
            budgets.extend(await self._budgets.list_for_target("user", user_id))
        keys = await self._vkeys.list_for_tenant(
            tenant_id, include_system=False, include_inactive=False
        )
        visible_keys = filter_virtual_keys_visible_to_actor(
            keys,
            actor_user_id=actor_user_id if actor_user_id is not None else user_id,
        )
        key_ids = [k.id for k in visible_keys]
        if key_ids:
            budgets.extend(await self._budgets.list_for_target_ids("key", key_ids))
        return budgets

    async def list_budgets_for_team_admin(
        self,
        tenant_id: UUID,
        *,
        include_system: bool = False,
        target_kind: str | None = None,
        model_name: str | None = None,
    ) -> list[GatewayBudget]:
        """Admin 读路径：团队 tenant + 成员 user + 团队 vkey + 可选 system。"""
        plan = plan_admin_budget_fetch(
            target_kind=target_kind,
            include_system=include_system,
        )
        budgets: list[GatewayBudget] = []

        if plan.fetch_tenant:
            budgets.extend(await self._budgets.list_for_target("tenant", tenant_id))

        if plan.fetch_user:
            user_ids = list(await self.list_team_member_user_ids(tenant_id))
            if user_ids:
                budgets.extend(await self._budgets.list_for_target_ids("user", user_ids))

        if plan.fetch_key:
            keys = await self._vkeys.list_for_tenant(
                tenant_id, include_system=True, include_inactive=True
            )
            key_ids = [k.id for k in keys]
            if key_ids:
                budgets.extend(await self._budgets.list_for_target_ids("key", key_ids))

        if plan.fetch_system:
            budgets.extend(await self._budgets.list_for_target("system", None))

        filters = normalize_budget_list_filters(target_kind, model_name)
        return filter_budget_rows(budgets, filters)

    async def list_team_member_user_ids(self, tenant_id: UUID) -> frozenset[UUID]:
        members = await self._teams.list_team_members(tenant_id)
        return frozenset(m.user_id for m in members)

    async def list_alert_rules(self, team_id: UUID) -> list[AlertRuleSummary]:
        rows = await self._alerts.list_rules_for_tenant(team_id)
        return [alert_rule_from_orm(r) for r in rows]

    async def list_alert_events_as_dicts(
        self, team_id: UUID, *, limit: int
    ) -> list[dict[str, Any]]:
        rows = await self._alerts.list_events_for_tenant(team_id, limit=limit)
        return [
            {
                "id": r.id,
                "rule_id": r.rule_id,
                "tenant_id": r.tenant_id,
                "team_id": r.tenant_id,
                "metric_value": float(r.metric_value),
                "threshold": float(r.threshold),
                "severity": r.severity,
                "payload": r.payload,
                "notified": r.notified,
                "acknowledged": r.acknowledged,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # ProviderPlan / EntitlementPlan reads
    #
    # 套餐列表/详情返回 application 读模型；presentation 再映射为 HTTP Schema。
    # ------------------------------------------------------------------
    async def list_provider_plans_with_quotas_for_credential(
        self, credential_id: UUID
    ) -> list[ProviderPlanReadModel]:
        rows = await self._provider_plans.list_with_quotas_for_credential(credential_id)
        return [provider_plan_from_orm(plan, quotas) for plan, quotas in rows]

    async def list_provider_plans_with_quotas_for_credentials(
        self, credential_ids: list[UUID]
    ) -> dict[UUID, list[ProviderPlanReadModel]]:
        rows_by_cred = await self._provider_plans.list_with_quotas_for_credentials(credential_ids)
        return {
            cred_id: [provider_plan_from_orm(plan, quotas) for plan, quotas in plan_rows]
            for cred_id, plan_rows in rows_by_cred.items()
        }

    async def list_entitlement_plans_with_quotas_for_scope(
        self, scope: str, scope_id: UUID
    ) -> list[EntitlementPlanReadModel]:
        rows = await self._entitlement_plans.list_with_quotas_for_scope(scope, scope_id)
        return [entitlement_plan_from_orm(plan, quotas) for plan, quotas in rows]

    async def list_entitlement_plans_with_quotas_for_vkeys(
        self, vkey_ids: list[UUID]
    ) -> dict[UUID, list[EntitlementPlanReadModel]]:
        rows_by_vkey = await self._entitlement_plans.list_with_quotas_for_vkeys(vkey_ids)
        return {
            vkey_id: [entitlement_plan_from_orm(plan, quotas) for plan, quotas in plan_rows]
            for vkey_id, plan_rows in rows_by_vkey.items()
        }

    async def get_provider_plan_with_quotas(self, plan_id: UUID) -> ProviderPlanReadModel | None:
        row = await self._provider_plans.get_with_quotas(plan_id)
        if row is None:
            return None
        plan, quotas = row
        return provider_plan_from_orm(plan, quotas)

    async def get_entitlement_plan_with_quotas(
        self, plan_id: UUID
    ) -> EntitlementPlanReadModel | None:
        row = await self._entitlement_plans.get_with_quotas(plan_id)
        if row is None:
            return None
        plan, quotas = row
        return entitlement_plan_from_orm(plan, quotas)

    async def get_entitlement_usage(
        self,
        plan_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> EntitlementUsageReadModel:
        return await self._plan_usage.get_entitlement_usage(plan_id, since=since, until=until)

    async def get_provider_plan_cost(
        self,
        plan_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> ProviderPlanCostReadModel:
        return await self._plan_usage.get_provider_plan_cost(plan_id, since=since, until=until)

    async def get_team_margin_summary(
        self,
        team_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        group_by: MarginGroupBy = "credential",
    ) -> MarginSummaryReadModel:
        return await self._plan_usage.get_team_margin_summary(
            team_id, since=since, until=until, group_by=group_by
        )

    async def list_platform_credential_stats(
        self,
        *,
        days: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """全平台凭据维度调用统计 + 各凭据被 GatewayModel 引用条数（仅平台管理员 HTTP 层应调用）。"""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        global_usage = await self._logs.aggregate_by_credential_global(start, end)
        counts: dict[UUID, int] = dict(await self._models.count_models_grouped_by_credential())
        for cid, cnt in await self._models.count_system_models_grouped_by_credential():
            counts[cid] = counts.get(cid, 0) + cnt
        all_ids = sorted(set(global_usage.keys()) | set(counts.keys()))
        if not all_ids:
            return [], 0
        creds = await self._creds.list_by_ids(all_ids)
        cred_by_id = {c.id: c for c in creds}
        missing_ids = {cid for cid in all_ids if cid not in cred_by_id}
        system_rows = await self._system_creds.list_by_ids(missing_ids)
        system_by_id = {row.id: row for row in system_rows}
        rows: list[dict[str, Any]] = []
        for cid in all_ids:
            g = global_usage.get(cid, {})
            sys_c = system_by_id.get(cid)
            c = cred_by_id.get(cid)
            if sys_c is not None:
                provider = sys_c.provider
                name = sys_c.name
                scope = CredentialScope.SYSTEM.value
                scope_id = None
                is_active = bool(sys_c.is_active)
            elif c is not None:
                provider = c.provider
                name = c.name
                scope = credential_api_scope(scope=c.scope, tenant_id=c.tenant_id)
                scope_id = c.scope_id
                is_active = bool(c.is_active)
            else:
                provider = ""
                name = "(已删除)"
                scope = "unknown"
                scope_id = None
                is_active = False
            rows.append(
                {
                    "credential_id": cid,
                    "provider": provider,
                    "name": name,
                    "scope": scope,
                    "scope_id": scope_id,
                    "is_active": is_active,
                    "gateway_model_count": int(counts.get(cid, 0)),
                    "requests": int(g.get("requests", 0)),
                    "input_tokens": int(g.get("input_tokens", 0)),
                    "output_tokens": int(g.get("output_tokens", 0)),
                    "cost_usd": g.get("cost_usd", Decimal("0")),
                    "success_count": int(g.get("success", 0)),
                    "failure_count": int(g.get("failure", 0)),
                }
            )
        rows.sort(key=lambda r: (-r["requests"], str(r["credential_id"])))
        return slice_page(rows, page=page, page_size=page_size)

    async def list_quota_rules_for_team(
        self,
        team_id: UUID,
        *,
        actor_user_id: UUID | None,
        team_role: str,
        is_platform_admin: bool,
        is_team_admin: bool,
        filters: QuotaRuleListFilters | None = None,
    ) -> list[QuotaRuleReadModel]:
        from domains.gateway.application.management.quota_rule_assembler import (
            assemble_team_quota_rules,
        )

        return await assemble_team_quota_rules(
            self,
            team_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
            is_team_admin=is_team_admin,
            filters=filters,
        )


__all__ = ["GatewayManagementReadService"]
