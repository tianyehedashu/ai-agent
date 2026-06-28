"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.catalog.model_reference_prune import (
    prune_gateway_model_name_references,
)
from domains.gateway.application.management.access_assertions import (
    GatewayManagementAccessAssertions,
)
from domains.gateway.domain.budget.budget_scope_policy import (
    BudgetTeamContext,
    budget_target_allowed,
)
from domains.gateway.domain.credential.team_credential_access import (
    actor_owns_team_credential,
)
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.types import BudgetScope
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_quota import ProviderQuota
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
    GatewayRouteTeamGrantRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.provider_quota_repository import (
    ProviderQuotaRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import ValidationError
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
        self._route_grants = GatewayRouteTeamGrantRepository(session)
        self._budgets = BudgetRepository(session)
        self._alerts = GatewayAlertRepository(session)
        self._provider_quotas = ProviderQuotaRepository(session)
        self._entitlement_plans = EntitlementPlanRepository(session)
        self._teams = TeamService(session)
        self._access = GatewayManagementAccessAssertions(
            session=session,
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

    async def _assert_user_owns_credential(
        self, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> None:
        cred = await self._creds.get(credential_id)
        if cred is None or cred.scope != "user" or cred.scope_id != user_id:
            raise CredentialNotFoundError(str(credential_id))

    async def _cascade_delete_provider_quotas_for_model(
        self,
        *,
        credential_id: uuid.UUID | None,
        real_model: str | None,
        exclude_tenant_model_id: uuid.UUID | None = None,
        exclude_system_model_id: uuid.UUID | None = None,
    ) -> int:
        """删除模型时清理上游配额：仅当同凭据 + real_model 无其它注册行时。"""
        if credential_id is None:
            return 0
        rm = (real_model or "").strip()
        if not rm:
            return 0
        remaining = await self._models.count_registrations_for_credential_real_model(
            credential_id,
            rm,
            exclude_tenant_model_id=exclude_tenant_model_id,
            exclude_system_model_id=exclude_system_model_id,
        )
        if remaining > 0:
            return 0
        return await self._provider_quotas.delete_all_for_credential_real_model(credential_id, rm)

    async def _rekey_provider_quotas_for_model(
        self,
        *,
        old_credential_id: uuid.UUID | None,
        new_credential_id: uuid.UUID | None,
        old_real_model: str,
        new_real_model: str,
    ) -> int:
        if old_credential_id is None or new_credential_id is None:
            return 0
        return await self._provider_quotas.rebind_quotas(
            old_credential_id=old_credential_id,
            old_real_model=old_real_model,
            new_credential_id=new_credential_id,
            new_real_model=new_real_model,
        )

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

    async def _cascade_sync_models_for_credential_is_active(
        self,
        credential_id: uuid.UUID,
        *,
        is_active: bool,
    ) -> int:
        """凭据启用/停用时，同步关联注册模型的 ``enabled``（见 ``credential_model_cascade``）。"""
        from domains.gateway.application.credential.credential_model_cascade import (
            sync_gateway_models_for_credential_is_active,
        )

        return await sync_gateway_models_for_credential_is_active(
            self._session,
            self._models,
            credential_id,
            is_active=is_active,
        )

    async def _assert_credential_in_team(
        self, credential_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool
    ) -> None:
        """与 ``list_credentials_for_team`` 可见集合一致：team-scope 凭据 + 平台管理员可见 system。"""
        await self._access.assert_credential_in_team(
            credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

    async def _assert_upstream_credential_writable(
        self,
        credential_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        request_tenant_id: uuid.UUID,
    ) -> uuid.UUID:
        """上游配额写权限与展示 team_id。

        - ``scope=user``：仅凭据所有者；展示 team = 所有者 personal team。
        - ``scope=team``：actor 对该 ``tenant_id`` 有 admin（或平台管理员）。
        - system：平台管理员；展示 team 回退为请求上下文团队。
        """
        from domains.tenancy.domain.policies.team_role import is_admin_or_owner_team_role

        row = await self._creds.get(credential_id)
        if row is not None:
            if row.scope == "user":
                if row.scope_id is None or row.scope_id != actor_user_id:
                    raise CredentialNotFoundError(str(credential_id))
                return await self._ensure_personal_tenant_id(row.scope_id)
            if row.tenant_id is None:
                raise ValidationError("upstream 配额仅支持团队或系统凭据")
            if is_platform_admin:
                return row.tenant_id
            memberships = await self._teams.list_gateway_team_memberships(
                actor_user_id,
                is_platform_admin=False,
            )
            for membership in memberships:
                if membership.team_id == row.tenant_id and is_admin_or_owner_team_role(
                    membership.role
                ):
                    return row.tenant_id
            raise CredentialNotFoundError(str(credential_id))

        if is_platform_admin:
            sys_row = await self._system_creds.get(credential_id)
            if sys_row is not None:
                return request_tenant_id
        raise CredentialNotFoundError(str(credential_id))

    async def _assert_credential_owned_by_actor(
        self, credential_id: uuid.UUID, *, actor_user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """成员自助配额：凭据须为本人 BYOK（``scope=user`` 且 ``scope_id==actor``）
        或本人在该团队创建的凭据（``created_by_user_id==actor``）。
        否则抛 ``CredentialNotFoundError``（防枚举他人凭据）。
        """
        cred = await self._creds.get(credential_id)
        if cred is None:
            raise CredentialNotFoundError(str(credential_id))
        if cred.scope == "user":
            if cred.scope_id == actor_user_id:
                return
            raise CredentialNotFoundError(str(credential_id))
        if cred.tenant_id == tenant_id and actor_owns_team_credential(
            created_by_user_id=cred.created_by_user_id,
            actor_user_id=actor_user_id,
        ):
            return
        raise CredentialNotFoundError(str(credential_id))

    async def _assert_model_alias_on_credential(
        self, credential_id: uuid.UUID, model_name: str
    ) -> None:
        """成员+凭据预算的 ``model_name`` 须为该凭据下已注册别名（路由虚拟名不可直接写入）。"""
        pairs = await self._models.list_name_real_model_pairs_for_credential(credential_id)
        if model_name not in {alias for alias, _ in pairs}:
            raise ValidationError(
                f"模型别名 {model_name!r} 未注册在该凭据下；多凭据路由请使用「别名--凭据」具体别名"
            )

    async def _resolve_registered_real_model(self, credential_id: uuid.UUID, model_ref: str) -> str:
        """将别名或 ``GatewayModel.real_model`` 归一为落库用的 canonical real_model。

        接受三种输入：
        - 已注册的 canonical real_model（精确匹配，如 ``openai/gpt-4o-mini``）
        - 已注册的别名（如 ``Quota BYOK Model``）
        - 裸上游模型 id（如 ``gpt-4o-mini``，匹配去掉 provider 前缀的 real_model）
          个人 BYOK 模型创建时用 ``model_id`` 入参，落库会加 provider 前缀；
          用户在配额规则里仍用原始 ``model_id`` 引用，需归一到 canonical real_model。
        """
        ref = model_ref.strip()
        pairs = await self._models.list_name_real_model_pairs_for_credential(credential_id)
        by_alias = dict(pairs)
        registered = {rm for _, rm in pairs}
        if ref in registered:
            return ref
        if ref in by_alias:
            return by_alias[ref]
        # 裸 id 匹配：ref 为去掉 provider 前缀的 real_model（如 "gpt-4o-mini" → "openai/gpt-4o-mini"）
        for rm in registered:
            if "/" in rm and rm.rsplit("/", 1)[1] == ref:
                return rm
        raise ValidationError(f"上游模型 {ref!r} 未注册在该凭据下")

    async def _assert_real_model_on_credential(
        self, credential_id: uuid.UUID, real_model: str
    ) -> None:
        """上游配额的 ``real_model`` 须为该凭据下已注册模型的 canonical id。"""
        await self._resolve_registered_real_model(credential_id, real_model)

    async def _assert_provider_quota_in_credential(
        self, rule_id: uuid.UUID, *, credential_id: uuid.UUID
    ) -> ProviderQuota:
        row = await self._provider_quotas.get(rule_id)
        if row is None or row.credential_id != credential_id:
            raise ManagementEntityNotFoundError("provider_quota", str(rule_id))
        return row

    async def _assert_vkey_in_team(
        self, vkey_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool
    ) -> None:
        record = await self._vkeys.get(vkey_id)
        if record is None:
            raise VirtualKeyNotFoundError(str(vkey_id))
        if not is_platform_admin and record.tenant_id != tenant_id:
            raise VirtualKeyNotFoundError(str(vkey_id))

    async def _assert_apikey_grant_in_team(
        self, grant_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool
    ) -> None:
        await self._access.assert_apikey_grant_in_team(
            grant_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

    async def _assert_entitlement_plan_in_team(
        self, plan_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool
    ) -> EntitlementPlan:
        plan = await self._entitlement_plans.get(plan_id)
        if plan is None:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        if plan.target_kind == "vkey":
            await self._assert_vkey_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        elif plan.target_kind == "apikey_grant":
            await self._assert_apikey_grant_in_team(
                plan.target_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
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
        # 团队轴：成员护栏行（tenant_id 非空）须属于当前团队，
        # 防止同一成员所在的其他团队管理员跨团队删除/操作。
        if budget.tenant_id is not None and budget.tenant_id != tenant_id:
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        # 凭据轴：成员+凭据行的凭据须在当前团队可见集合内（凭据天然绑定团队）。
        if budget.credential_id is not None:
            try:
                await self._assert_credential_in_team(
                    budget.credential_id,
                    tenant_id=tenant_id,
                    is_platform_admin=is_platform_admin,
                )
            except CredentialNotFoundError as exc:
                raise ManagementEntityNotFoundError("budget", str(budget_id)) from exc

    async def _invalidate_quota_rule_list_cache(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        upstream_changed: bool = False,
    ) -> None:
        """失效配额中心列表缓存。

        上游规则在 assembler 中按 actor 跨团队聚合，写入任一团队后须刷新 actor
        全部 membership 团队的列表缓存，否则其它团队页仍命中旧快照。
        """
        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_provider_quota_config_cache,
            invalidate_gateway_quota_rule_cache_for_team,
        )

        if upstream_changed:
            await invalidate_gateway_provider_quota_config_cache()

        team_ids: set[uuid.UUID] = {tenant_id}
        if upstream_changed and actor_user_id is not None:
            memberships = await self._teams.list_gateway_team_memberships(
                actor_user_id,
                is_platform_admin=False,
            )
            team_ids.update(m.team_id for m in memberships)
        for team_id in team_ids:
            await invalidate_gateway_quota_rule_cache_for_team(team_id)

    async def _invalidate_upstream_quota_rule_list_cache(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
    ) -> None:
        """上游 ProviderQuota 变更后失效配额中心列表缓存（含 actor 各 membership 团队）。"""
        await self._invalidate_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            upstream_changed=True,
        )

    async def reload_litellm_router(self, *, tenant_id: uuid.UUID | None = None) -> None:
        from domains.gateway.application.grant.resolve_model_cache import invalidate_all
        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_read_caches_for_tenant,
        )
        from domains.gateway.application.route.route_snapshot_cache import (
            clear_route_snapshot_cache_for_tests,
        )
        from libs.db.database import commit_pending_writes

        # 只提交凭据/模型等写入以释放唯一索引锁；Router 重载为只读，不必 rollback 只读事务。
        await commit_pending_writes(self._session)

        if tenant_id is not None:
            invalidate_gateway_read_caches_for_tenant(tenant_id)
            await self._invalidate_shared_route_consumer_caches(exclude=tenant_id)
        else:
            invalidate_all()
            clear_route_snapshot_cache_for_tests()

        from domains.gateway.infrastructure.litellm.router_reload_notifier import (
            publish_router_reload,
        )
        from domains.gateway.infrastructure.litellm.router_singleton import reload_router

        try:
            await reload_router(self._session)
            # 本地重载成功后，发布跨进程事件，通知其他 worker 同步重载并按
            # tenant_id 失效 L1 缓存（多 worker 部署下凭据/模型/路由变更必须广播）
            await publish_router_reload(source="mgmt_write", tenant_id=tenant_id)
        except Exception:
            logger.exception("LiteLLM Router reload failed")

    async def _invalidate_shared_route_consumer_caches(
        self, *, exclude: uuid.UUID | None = None
    ) -> None:
        """失效持有共享路由的消费团队 resolve 缓存。

        委派解析结果按消费团队 ``(T, user, alias)`` 键缓存，而 owner 侧改/禁用底层模型时
        只会失效 owner 自身租户，遗漏 T。这里在租户级 reload 时连带失效所有消费团队，
        保证「owner 改路由底层资源对 T 实时生效」（D4）。grant 表规模小，开销可忽略。
        """
        from bootstrap.config import settings

        if not settings.gateway_route_sharing_enabled:
            return
        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_read_caches_for_tenant,
        )

        consumer_tenant_ids = await self._route_grants.list_active_consumer_tenant_ids()
        for consumer_tenant_id in consumer_tenant_ids:
            if consumer_tenant_id != exclude:
                invalidate_gateway_read_caches_for_tenant(consumer_tenant_id)

    def invalidate_tenant_gateway_read_caches(self, tenant_id: uuid.UUID) -> None:
        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_read_caches_for_tenant,
        )

        invalidate_gateway_read_caches_for_tenant(tenant_id)
