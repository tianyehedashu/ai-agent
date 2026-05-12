"""Gateway 管理面读模型（CQRS Query）"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.team_service import TeamService
from domains.gateway.domain.errors import TeamPermissionDeniedError
from domains.gateway.domain.types import ManagementTeamContext
from domains.gateway.infrastructure.models.alert import GatewayAlertRule
from domains.gateway.infrastructure.models.team import Team, TeamMember
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
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
from domains.gateway.infrastructure.repositories.team_repository import TeamMemberRepository
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)


class GatewayManagementQueryService:
    """管理 API 只读用例，经仓储访问数据"""

    def __init__(self, session: AsyncSession) -> None:
        self._teams = TeamService(session)
        self._members = TeamMemberRepository(session)
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._logs = RequestLogRepository(session)
        self._alerts = GatewayAlertRepository(session)

    async def list_teams_with_roles_for_user(
        self, user_id: uuid.UUID
    ) -> list[tuple[Team, str | None]]:
        teams = await self._teams.list_user_teams(user_id)
        items: list[tuple[Team, str | None]] = []
        for t in teams:
            member = await self._members.get(t.id, user_id)
            items.append((t, member.role if member else None))
        return items

    async def get_team(self, team_id: uuid.UUID) -> Team | None:
        return await self._teams.get_team(team_id)

    async def list_team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        return await self._members.list_by_team(team_id)

    async def list_virtual_keys_for_team(
        self, team_id: uuid.UUID
    ) -> list[GatewayVirtualKey]:
        return await self._vkeys.list_by_team(
            team_id, include_system=False, include_inactive=True
        )

    async def list_credentials_for_team(
        self, team_id: uuid.UUID, *, include_system: bool
    ) -> list[Any]:
        return await self._creds.list_for_team(team_id, include_system=include_system)

    async def list_gateway_models(
        self, team_id: uuid.UUID, *, only_enabled: bool
    ) -> list[Any]:
        return await self._models.list_for_team(team_id, only_enabled=only_enabled)

    async def list_gateway_routes(
        self, team_id: uuid.UUID, *, only_enabled: bool
    ) -> list[Any]:
        return await self._routes.list_for_team(team_id, only_enabled=only_enabled)

    async def list_budgets_for_team_and_user(
        self, team_id: uuid.UUID, user_id: uuid.UUID | None
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
        page: int,
        page_size: int,
        start: datetime | None,
        end: datetime | None,
        status_filter: str | None,
        capability: str | None,
        vkey_id: uuid.UUID | None,
    ) -> tuple[list[Any], int]:
        items, total = await self._logs.list_for_team(
            ctx.team_id,
            start=start,
            end=end,
            status=status_filter,
            capability=capability,
            vkey_id=vkey_id,
            page=page,
            page_size=page_size,
        )
        if (
            not ctx.is_platform_admin
            and ctx.team_role == "member"
            and vkey_id is None
        ):
            my_keys = await self._vkeys.list_by_team(ctx.team_id)
            my_ids = {
                k.id
                for k in my_keys
                if k.created_by_user_id == ctx.user_id and not k.is_system
            }
            items = [i for i in items if i.vkey_id in my_ids]
        return items, total

    async def get_request_log_for_team(
        self, ctx: ManagementTeamContext, log_id: uuid.UUID
    ) -> Any | None:
        record = await self._logs.get_for_team(log_id, ctx.team_id)
        if record is None:
            return None
        if not ctx.is_platform_admin and ctx.team_role == "member":
            my_keys = await self._vkeys.list_by_team(ctx.team_id)
            my_ids = {
                k.id
                for k in my_keys
                if k.created_by_user_id == ctx.user_id and not k.is_system
            }
            if record.vkey_id not in my_ids:
                raise TeamPermissionDeniedError(str(ctx.team_id))
        return record

    async def aggregate_request_log_summary(
        self, team_id: uuid.UUID, start: datetime, end: datetime
    ) -> dict[str, Any]:
        return await self._logs.aggregate_summary(team_id, start, end)

    async def list_alert_rules(self, team_id: uuid.UUID) -> list[GatewayAlertRule]:
        return await self._alerts.list_rules_by_team(team_id)

    async def list_alert_events_as_dicts(
        self, team_id: uuid.UUID, *, limit: int
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


__all__ = ["GatewayManagementQueryService"]
