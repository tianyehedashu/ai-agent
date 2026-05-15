"""Gateway 管理面只读应用服务（CQRS 读侧的工程分包；对外语义见架构文档术语表）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from domains.gateway.application.management.usage_metrics import merge_gateway_usage_slices
from domains.gateway.domain.errors import CredentialNotFoundError, TeamPermissionDeniedError
from domains.gateway.domain.usage_read_model import UsageAggregation
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from libs.iam.tenancy import MembershipPort

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.alert import GatewayAlertRule
    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
    from domains.tenancy.domain.management_context import ManagementTeamContext
    from domains.tenancy.infrastructure.models.team import Team, TeamMember


class GatewayManagementReadService:
    """管理 API 只读用例，经仓储访问数据"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        membership: MembershipPort | None = None,
    ) -> None:
        self._session = session
        self._membership = membership or TenancyMembershipAdapter()
        self._teams = TeamService(session, membership=self._membership)
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._logs = RequestLogRepository(session)
        self._alerts = GatewayAlertRepository(session)

    async def list_teams_with_roles_for_user(
        self, user_id: UUID
    ) -> list[tuple[Team, str | None]]:
        return await self._teams.list_teams_with_roles_for_user(user_id)

    async def get_team(self, team_id: UUID) -> Team | None:
        return await self._teams.get_team(team_id)

    async def list_team_members(self, team_id: UUID) -> list[TeamMember]:
        return await self._teams.list_team_members(team_id)

    async def list_virtual_keys_for_team(self, team_id: UUID) -> list[GatewayVirtualKey]:
        return await self._vkeys.list_by_team(team_id, include_system=False, include_inactive=True)

    async def list_credentials_for_team(
        self, team_id: UUID, *, include_system: bool
    ) -> list[ProviderCredential]:
        return await self._creds.list_for_team(team_id, include_system=include_system)

    async def get_managed_credential_for_team(
        self,
        credential_id: UUID,
        *,
        team_id: UUID,
        is_platform_admin: bool,
    ) -> ProviderCredential:
        """与 ``list_credentials_for_team`` 可见集合一致：团队凭据 +（仅平台管理员）系统凭据。"""
        row = await self._creds.get(credential_id)
        if row is None:
            raise CredentialNotFoundError(str(credential_id))
        if row.scope == "team":
            if row.scope_id != team_id:
                raise CredentialNotFoundError(str(credential_id))
            return row
        if row.scope == "system":
            if not is_platform_admin:
                raise CredentialNotFoundError(str(credential_id))
            return row
        raise CredentialNotFoundError(str(credential_id))

    async def list_user_credentials(self, user_id: UUID) -> list[ProviderCredential]:
        return await self._creds.list_for_user(user_id)

    async def list_gateway_models(
        self,
        team_id: UUID,
        *,
        only_enabled: bool,
        provider: str | None = None,
        credential_id: UUID | None = None,
    ) -> list[GatewayModel]:
        return await self._models.list_for_team(
            team_id,
            only_enabled=only_enabled,
            provider=provider,
            credential_id=credential_id,
        )

    async def list_gateway_routes(self, team_id: UUID, *, only_enabled: bool) -> list[Any]:
        return await self._routes.list_for_team(team_id, only_enabled=only_enabled)

    async def list_budgets_for_team_and_user(
        self, team_id: UUID, user_id: UUID | None
    ) -> list[Any]:
        budgets: list[Any] = []
        budgets.extend(await self._budgets.list_for_scope("team", team_id))
        if user_id is not None:
            budgets.extend(await self._budgets.list_for_scope("user", user_id))
        return budgets

    async def list_request_logs(
        self,
        ctx: ManagementTeamContext,
        *,
        usage_aggregation: UsageAggregation,
        page: int,
        page_size: int,
        start: datetime | None,
        end: datetime | None,
        status_filter: str | None,
        capability: str | None,
        vkey_id: UUID | None,
        credential_id: UUID | None = None,
    ) -> tuple[list[Any], int]:
        if usage_aggregation == UsageAggregation.USER:
            items, total = await self._logs.list_for_user(
                ctx.user_id,
                start=start,
                end=end,
                status=status_filter,
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                page=page,
                page_size=page_size,
            )
        else:
            apply_member_workspace_scope = (
                usage_aggregation == UsageAggregation.WORKSPACE
                and not ctx.is_platform_admin
                and ctx.team_role == "member"
                and vkey_id is None
            )
            items, total = await self._logs.list_for_team(
                ctx.team_id,
                start=start,
                end=end,
                status=status_filter,
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                page=page,
                page_size=page_size,
                workspace_member_user_id=ctx.user_id if apply_member_workspace_scope else None,
            )
        return items, total

    async def get_request_log(
        self,
        ctx: ManagementTeamContext,
        log_id: UUID,
        *,
        usage_aggregation: UsageAggregation,
    ) -> Any | None:
        if usage_aggregation == UsageAggregation.USER:
            return await self._logs.get_for_user(log_id, ctx.user_id)

        record = await self._logs.get_for_team(log_id, ctx.team_id)
        if record is None:
            return None
        if not ctx.is_platform_admin and ctx.team_role == "member":
            if record.vkey_id is None:
                allowed = record.user_id == ctx.user_id
            else:
                allowed = await self._vkeys.is_non_system_vkey_owned_by_user_on_team(
                    record.vkey_id,
                    team_id=ctx.team_id,
                    user_id=ctx.user_id,
                )
            if not allowed:
                raise TeamPermissionDeniedError(str(ctx.team_id))
        return record

    async def get_request_log_for_team(
        self, ctx: ManagementTeamContext, log_id: UUID
    ) -> Any | None:
        return await self.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)

    async def aggregate_request_log_summary(
        self,
        ctx: ManagementTeamContext,
        start: datetime,
        end: datetime,
        *,
        usage_aggregation: UsageAggregation,
    ) -> dict[str, Any]:
        if usage_aggregation == UsageAggregation.USER:
            return await self._logs.aggregate_summary_for_user(ctx.user_id, start, end)
        return await self._logs.aggregate_summary(ctx.team_id, start, end)

    async def list_alert_rules(self, team_id: UUID) -> list[GatewayAlertRule]:
        return await self._alerts.list_rules_by_team(team_id)

    async def list_alert_events_as_dicts(
        self, team_id: UUID, *, limit: int
    ) -> list[dict[str, Any]]:
        rows = await self._alerts.list_events_by_team(team_id, limit=limit)
        return [
            {
                "id": str(r.id),
                "rule_id": str(r.rule_id),
                "metric_value": float(r.metric_value),
                "threshold": float(r.threshold),
                "severity": r.severity,
                "payload": r.payload,
                "notified": r.notified,
                "acknowledged": r.acknowledged,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    async def aggregate_gateway_model_route_usage(
        self,
        ctx: ManagementTeamContext,
        *,
        days: int,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """按注册模型聚合用量：``deployment_gateway_model_id``（经路由命中）+ 仅 ``route_name`` 的历史/直连行。

        与 ``GatewayModel`` 列表行一一对应；``route_name`` 可为客户端虚拟名，与注册 ``name`` 不同。
        """
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        models = await self._models.list_for_team(
            ctx.team_id, only_enabled=False, provider=provider
        )
        if not models:
            return {"start": start, "end": end, "items": []}
        models_sorted = sorted(models, key=lambda m: (m.name, str(m.id)))[:500]
        route_names = [m.name for m in models_sorted]
        model_ids = [m.id for m in models_sorted]
        by_ws_route = await self._logs.aggregate_by_route_names_for_team(
            ctx.team_id, route_names, start, end
        )
        by_user_route = await self._logs.aggregate_by_route_names_for_user(
            ctx.user_id, route_names, start, end
        )
        by_ws_dep = await self._logs.aggregate_by_deployment_gateway_model_ids_for_team(
            ctx.team_id, model_ids, start, end
        )
        by_user_dep = await self._logs.aggregate_by_deployment_gateway_model_ids_for_user(
            ctx.user_id, model_ids, start, end
        )
        items: list[dict[str, Any]] = []
        for m in models_sorted:
            name = m.name
            w = merge_gateway_usage_slices(
                by_ws_dep.get(m.id, {}),
                by_ws_route.get(name, {}),
            )
            u = merge_gateway_usage_slices(
                by_user_dep.get(m.id, {}),
                by_user_route.get(name, {}),
            )
            items.append(
                {
                    "route_name": name,
                    "workspace": {
                        "requests": int(w["requests"]),
                        "input_tokens": int(w["input_tokens"]),
                        "output_tokens": int(w["output_tokens"]),
                        "cost_usd": w["cost_usd"],
                    },
                    "user": {
                        "requests": int(u["requests"]),
                        "input_tokens": int(u["input_tokens"]),
                        "output_tokens": int(u["output_tokens"]),
                        "cost_usd": u["cost_usd"],
                    },
                }
            )
        return {"start": start, "end": end, "items": items}

    async def list_platform_credential_stats(self, *, days: int) -> list[dict[str, Any]]:
        """全平台凭据维度调用统计 + 各凭据被 GatewayModel 引用条数（仅平台管理员 HTTP 层应调用）。"""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        global_usage = await self._logs.aggregate_by_credential_global(start, end)
        counts_list = await self._models.count_models_grouped_by_credential()
        counts: dict[UUID, int] = dict(counts_list)
        all_ids = sorted(set(global_usage.keys()) | set(counts.keys()))
        if not all_ids:
            return []
        creds = await self._creds.list_by_ids(all_ids)
        cred_by_id = {c.id: c for c in creds}
        rows: list[dict[str, Any]] = []
        for cid in all_ids:
            g = global_usage.get(cid, {})
            c = cred_by_id.get(cid)
            rows.append(
                {
                    "credential_id": cid,
                    "provider": c.provider if c else "",
                    "name": c.name if c else "(已删除)",
                    "scope": c.scope if c else "",
                    "scope_id": c.scope_id if c else None,
                    "is_active": bool(c.is_active) if c else False,
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
        return rows


__all__ = ["GatewayManagementReadService"]
