"""Gateway 管理面：请求日志与用量聚合只读（mixin）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from domains.gateway.application.management.usage_metrics import merge_gateway_usage_slices
from domains.gateway.domain.errors import TeamPermissionDeniedError
from domains.gateway.domain.policies.usage_log_visibility import (
    member_can_view_request_log_record,
    usage_log_access_from_management_ctx,
    workspace_axis_member_user_id,
)
from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.domain.usage_read_model import UsageAggregation

if TYPE_CHECKING:
    from domains.tenancy.domain.management_context import ManagementTeamContext


class GatewayUsageLogReadMixin:
    """``GatewayManagementReadService`` 的日志/用量读方法。"""

    @staticmethod
    def _resolve_usage_axis(
        ctx: ManagementTeamContext,
        aggregation: UsageAggregation,
        *,
        vkey_id: UUID | None = None,
    ) -> UsageAxis:
        if aggregation == UsageAggregation.USER:
            return UsageAxis.user(ctx.user_id)
        snapshot = usage_log_access_from_management_ctx(ctx)
        member_user_id = workspace_axis_member_user_id(snapshot, vkey_id=vkey_id)
        return UsageAxis.workspace(ctx.team_id, member_user_id=member_user_id)

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
        axis = self._resolve_usage_axis(ctx, usage_aggregation, vkey_id=vkey_id)
        return await self._logs.list_by_axis(
            axis,
            start=start,
            end=end,
            status=status_filter,
            capability=capability,
            vkey_id=vkey_id,
            credential_id=credential_id,
            page=page,
            page_size=page_size,
        )

    async def get_request_log(
        self,
        ctx: ManagementTeamContext,
        log_id: UUID,
        *,
        usage_aggregation: UsageAggregation,
    ) -> Any | None:
        if usage_aggregation == UsageAggregation.USER:
            axis = UsageAxis.user(ctx.user_id)
        else:
            axis = UsageAxis.workspace(ctx.team_id)
        record = await self._logs.get_by_axis(axis, log_id)
        if record is None or usage_aggregation == UsageAggregation.USER:
            return record
        snapshot = usage_log_access_from_management_ctx(ctx)
        vkey_owned = False
        if record.vkey_id is not None:
            vkey_owned = await self._vkeys.is_non_system_vkey_owned_by_user_on_team(
                record.vkey_id,
                team_id=ctx.team_id,
                user_id=ctx.user_id,
            )
        if not member_can_view_request_log_record(
            snapshot,
            record_user_id=record.user_id,
            record_has_vkey=record.vkey_id is not None,
            vkey_owned_by_user=vkey_owned,
        ):
            raise TeamPermissionDeniedError(str(ctx.team_id))
        return record

    async def aggregate_request_log_summary(
        self,
        ctx: ManagementTeamContext,
        start: datetime,
        end: datetime,
        *,
        usage_aggregation: UsageAggregation,
    ) -> dict[str, Any]:
        axis = self._resolve_usage_axis(ctx, usage_aggregation)
        summary = await self._logs.aggregate_summary_by_axis(axis, start, end)
        summary["by_client_type"] = await self._logs.aggregate_by_client_type(axis, start, end)
        return summary

    async def aggregate_gateway_model_route_usage(
        self,
        ctx: ManagementTeamContext,
        *,
        days: int,
        provider: str | None = None,
    ) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        models = await self._models.list_for_tenant(
            ctx.team_id, only_enabled=False, provider=provider
        )
        if not models:
            return {"start": start, "end": end, "items": []}
        models_sorted = sorted(models, key=lambda m: (m.name, str(m.id)))[:500]
        route_names = [m.name for m in models_sorted]
        model_ids = [m.id for m in models_sorted]
        ws_axis = UsageAxis.workspace(ctx.team_id)
        u_axis = UsageAxis.user(ctx.user_id)
        by_ws_route = await self._logs.aggregate_by_route_names_by_axis(
            ws_axis, route_names, start, end
        )
        by_user_route = await self._logs.aggregate_by_route_names_by_axis(
            u_axis, route_names, start, end
        )
        by_ws_dep = await self._logs.aggregate_by_deployment_ids_by_axis(
            ws_axis, model_ids, start, end
        )
        by_user_dep = await self._logs.aggregate_by_deployment_ids_by_axis(
            u_axis, model_ids, start, end
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


__all__ = ["GatewayUsageLogReadMixin"]
