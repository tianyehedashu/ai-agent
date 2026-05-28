"""Gateway 管理面：请求日志与用量聚合只读（mixin）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from domains.gateway.application.gateway_model_listing import list_merged_models_for_tenant
from domains.gateway.application.management.usage_metrics import merge_gateway_usage_slices
from domains.gateway.application.management.usage_reads import (
    UsageStatisticsBreakdownSlice,
    UsageStatisticsBreakdownSummary,
    UsageStatisticsItem,
    UsageStatisticsMetric,
    UsageStatisticsSummary,
)
from domains.gateway.domain.errors import TeamPermissionDeniedError
from domains.gateway.domain.policies.usage_log_visibility import (
    member_can_view_request_log_record,
    usage_log_access_from_management_ctx,
    workspace_axis_member_user_id,
)
from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.domain.usage_read_model import (
    UsageAggregation,
    UsageStatisticsBreakdownBy,
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
    UsageStatisticsParentScope,
)
from domains.gateway.domain.usage_statistics_breakdown import (
    breakdown_by_to_group_by,
    normalize_usage_statistics_parent_group_key,
)
from domains.gateway.domain.virtual_key_access import actor_owns_non_system_vkey
from domains.identity.application.ports import user_display_label
from libs.api.pagination import slice_page

if TYPE_CHECKING:
    from domains.gateway.infrastructure.repositories.request_log_repository import (
        RequestLogUsageAggregateRow,
        RequestLogUsageTotals,
    )
    from domains.tenancy.domain.management_context import ManagementTeamContext


class GatewayUsageLogReadMixin:
    """``GatewayManagementReadService`` 的日志/用量读方法。"""

    @staticmethod
    def _workspace_axis_for_detail_fetch(ctx: ManagementTeamContext) -> UsageAxis:
        """单条详情：先按团队宽轴取行，再由 policy 区分 404/403。"""
        return UsageAxis.workspace(ctx.team_id)

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
        axis = (
            self._resolve_usage_axis(ctx, UsageAggregation.USER)
            if usage_aggregation == UsageAggregation.USER
            else self._workspace_axis_for_detail_fetch(ctx)
        )
        record = await self._logs.get_by_axis(axis, log_id)
        if record is None or usage_aggregation == UsageAggregation.USER:
            return record
        snapshot = usage_log_access_from_management_ctx(ctx)
        vkey_owned = False
        if record.vkey_id is not None:
            vkey = await self._vkeys.get(record.vkey_id)
            vkey_owned = (
                vkey is not None
                and vkey.tenant_id == ctx.team_id
                and actor_owns_non_system_vkey(
                    created_by_user_id=vkey.created_by_user_id,
                    actor_user_id=ctx.user_id,
                    is_system=vkey.is_system,
                )
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

    @staticmethod
    def _group_key_to_str(value: object) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _metric_from_totals(row: RequestLogUsageTotals) -> UsageStatisticsMetric:
        return UsageStatisticsMetric(
            requests=row.requests,
            success_count=row.success_count,
            failure_count=row.failure_count,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cached_tokens=row.cached_tokens,
            cost_usd=row.cost_usd,
            avg_latency_ms=row.avg_latency_ms,
            cache_hit_count=row.cache_hit_count,
        )

    @staticmethod
    def _item_from_row(row: RequestLogUsageAggregateRow, label: str) -> UsageStatisticsItem:
        return UsageStatisticsItem(
            group_key=GatewayUsageLogReadMixin._group_key_to_str(row.group_key),
            label=label,
            group_key_parts=row.group_key_parts,
            label_parts=row.label_parts,
            requests=row.requests,
            success_count=row.success_count,
            failure_count=row.failure_count,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cached_tokens=row.cached_tokens,
            cost_usd=row.cost_usd,
            avg_latency_ms=row.avg_latency_ms,
            cache_hit_count=row.cache_hit_count,
        )

    async def _usage_statistics_labels(
        self,
        rows: list[RequestLogUsageAggregateRow],
        group_by: UsageStatisticsGroupBy,
    ) -> dict[str, str]:
        labels: dict[str, str] = {}
        if group_by == UsageStatisticsGroupBy.CREDENTIAL:
            credential_ids = [row.group_key for row in rows if isinstance(row.group_key, UUID)]
            regular = await self._creds.list_by_ids(credential_ids)
            labels.update({str(row.id): row.name for row in regular})
            missing = [cid for cid in credential_ids if str(cid) not in labels]
            system = await self._system_creds.list_by_ids(missing)
            labels.update({str(row.id): row.name for row in system})
            for row in rows:
                key = self._group_key_to_str(row.group_key)
                if key in labels:
                    continue
                labels[key] = row.label_snapshot or ("未关联凭据" if not key else "已删除凭据")
            return labels

        if group_by == UsageStatisticsGroupBy.TEAM:
            team_ids = [row.group_key for row in rows if isinstance(row.group_key, UUID)]
            names = await self._teams.get_display_names_by_ids(team_ids)
            labels.update({str(key): value for key, value in names.items()})
            for row in rows:
                key = self._group_key_to_str(row.group_key)
                labels.setdefault(key, "未知团队" if key else "未关联团队")
            return labels

        if group_by == UsageStatisticsGroupBy.USER:
            user_ids = [row.group_key for row in rows if isinstance(row.group_key, UUID)]
            resolved: dict[str, str] = {}
            if user_ids:
                summaries = await self._user_summaries.list_summary_views_by_ids(user_ids)
                for uid, summary in summaries.items():
                    display = user_display_label(summary)
                    if display:
                        resolved[str(uid)] = display
            for row in rows:
                key = self._group_key_to_str(row.group_key)
                labels[key] = (
                    row.label_snapshot or resolved.get(key) or ("未知人员" if key else "未关联人员")
                )
            return labels

        for row in rows:
            key = self._group_key_to_str(row.group_key)
            if group_by == UsageStatisticsGroupBy.VKEY:
                labels[key] = row.label_snapshot or (
                    "平台 Key / 内部调用" if not key else "已删除 Key"
                )
            elif group_by == UsageStatisticsGroupBy.MODEL:
                labels[key] = key or "未关联模型"
            elif group_by == UsageStatisticsGroupBy.PROVIDER:
                labels[key] = key or "未知提供商"
            elif group_by == UsageStatisticsGroupBy.CAPABILITY:
                labels[key] = key or "未知能力"
            elif group_by == UsageStatisticsGroupBy.STATUS:
                labels[key] = key or "未知状态"
        return labels

    async def _build_user_model_credential_items(
        self,
        rows: list[RequestLogUsageAggregateRow],
    ) -> list[UsageStatisticsItem]:
        """为 USER_MODEL_CREDENTIAL 组合维度组装分组行，解析用户与凭据权威标签。"""
        from contextlib import suppress
        from uuid import UUID as _UUID

        user_ids: list[_UUID] = []
        credential_ids: list[_UUID] = []
        for row in rows:
            if isinstance(row.group_key, _UUID):
                user_ids.append(row.group_key)
            if row.group_key_parts and len(row.group_key_parts) > 2:
                with suppress(ValueError):
                    credential_ids.append(_UUID(row.group_key_parts[2]))

        user_labels: dict[str, str] = {}
        if user_ids:
            summaries = await self._user_summaries.list_summary_views_by_ids(user_ids)
            for uid, summary in summaries.items():
                display = user_display_label(summary)
                if display:
                    user_labels[str(uid)] = display

        cred_labels: dict[str, str] = {}
        if credential_ids:
            regular = await self._creds.list_by_ids(credential_ids)
            cred_labels.update({str(row.id): row.name for row in regular})
            missing = [cid for cid in credential_ids if str(cid) not in cred_labels]
            if missing:
                system = await self._system_creds.list_by_ids(missing)
                cred_labels.update({str(row.id): row.name for row in system})

        items: list[UsageStatisticsItem] = []
        for row in rows:
            key = self._group_key_to_str(row.group_key)
            parts = row.group_key_parts or [key, "", ""]
            user_label = (
                user_labels.get(key)
                or (row.label_parts[0] if row.label_parts else "")
                or ("未知人员" if key else "未关联人员")
            )
            model_label = parts[1] or "未关联模型"
            cred_key = parts[2] if len(parts) > 2 else ""
            cred_label = (
                cred_labels.get(cred_key)
                or (row.label_parts[2] if row.label_parts and len(row.label_parts) > 2 else "")
                or ("未关联凭据" if not cred_key else "已删除凭据")
            )
            label_parts = [user_label, model_label, cred_label]
            label = f"{user_label} / {model_label} / {cred_label}"
            items.append(
                UsageStatisticsItem(
                    group_key=key,
                    label=label,
                    group_key_parts=parts,
                    label_parts=label_parts,
                    requests=row.requests,
                    success_count=row.success_count,
                    failure_count=row.failure_count,
                    input_tokens=row.input_tokens,
                    output_tokens=row.output_tokens,
                    cached_tokens=row.cached_tokens,
                    cost_usd=row.cost_usd,
                    avg_latency_ms=row.avg_latency_ms,
                    cache_hit_count=row.cache_hit_count,
                )
            )
        return items

    async def aggregate_usage_statistics(
        self,
        ctx: ManagementTeamContext,
        start: datetime,
        end: datetime,
        *,
        usage_aggregation: UsageAggregation,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        page: int,
        page_size: int,
    ) -> tuple[UsageStatisticsSummary, int]:
        axis = self._resolve_usage_axis(
            ctx,
            usage_aggregation,
            vkey_id=filters.vkey_id,
        )
        rows, totals, group_total = await self._logs.aggregate_usage_statistics_by_axis(
            axis,
            start,
            end,
            group_by=group_by,
            filters=filters,
            page=page,
            page_size=page_size,
        )
        if group_by == UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL:
            items = await self._build_user_model_credential_items(rows)
        else:
            labels = await self._usage_statistics_labels(rows, group_by)
            items = [
                self._item_from_row(row, labels.get(self._group_key_to_str(row.group_key), "未知"))
                for row in rows
            ]
        summary = UsageStatisticsSummary(
            start=start,
            end=end,
            group_by=group_by,
            totals=self._metric_from_totals(totals),
            items=items,
        )
        return summary, group_total

    async def aggregate_usage_statistics_breakdown(
        self,
        ctx: ManagementTeamContext,
        start: datetime,
        end: datetime,
        *,
        usage_aggregation: UsageAggregation,
        filters: UsageStatisticsFilters,
        parent_group_by: UsageStatisticsGroupBy,
        parent_group_key: str,
        breakdown_by: UsageStatisticsBreakdownBy,
        top_n: int,
    ) -> UsageStatisticsBreakdownSummary:
        normalized_parent_key = normalize_usage_statistics_parent_group_key(
            parent_group_by,
            parent_group_key,
        )
        breakdown_group_by = breakdown_by_to_group_by(breakdown_by)
        axis = self._resolve_usage_axis(
            ctx,
            usage_aggregation,
            vkey_id=filters.vkey_id,
        )
        parent_scope = UsageStatisticsParentScope(
            group_by=parent_group_by,
            group_key=normalized_parent_key,
        )
        parent_requests = await self._logs.count_usage_requests_by_axis(
            axis,
            start,
            end,
            filters=filters,
            parent_scope=parent_scope,
        )
        rows, _, _ = await self._logs.aggregate_usage_statistics_by_axis(
            axis,
            start,
            end,
            group_by=breakdown_group_by,
            filters=filters,
            page=1,
            page_size=top_n,
            parent_scope=parent_scope,
        )
        labels = await self._usage_statistics_labels(rows, breakdown_group_by)
        items: list[UsageStatisticsBreakdownSlice] = []
        for row in rows:
            key = self._group_key_to_str(row.group_key)
            label = labels.get(key, "未知")
            share = (row.requests / parent_requests) if parent_requests > 0 else 0.0
            items.append(
                UsageStatisticsBreakdownSlice(
                    group_key=key,
                    label=label,
                    requests=row.requests,
                    share=share,
                )
            )
        return UsageStatisticsBreakdownSummary(
            parent_group_by=parent_group_by,
            parent_group_key=normalized_parent_key,
            breakdown_by=breakdown_by,
            parent_requests=parent_requests,
            items=items,
        )

    async def aggregate_gateway_model_route_usage(
        self,
        ctx: ManagementTeamContext,
        *,
        days: int,
        provider: str | None = None,
        route_names: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, datetime, datetime]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        models = await list_merged_models_for_tenant(
            self._session,
            ctx.team_id,
            only_enabled=False,
            provider=provider,
            user_id=ctx.user_id,
        )
        if not models:
            return [], 0, start, end
        models_sorted = sorted(models, key=lambda m: (m.name, str(m.id)))
        if route_names is not None:
            route_set = set(route_names)
            models_page = [m for m in models_sorted if m.name in route_set]
            total = len(models_page)
        else:
            models_page, total = slice_page(models_sorted, page=page, page_size=page_size)
        if not models_page:
            return [], total, start, end
        page_route_names = [m.name for m in models_page]
        model_ids = [m.id for m in models_page]
        snapshot = usage_log_access_from_management_ctx(ctx)
        member_user_id = workspace_axis_member_user_id(snapshot)
        ws_axis = UsageAxis.workspace(ctx.team_id, member_user_id=member_user_id)
        u_axis = UsageAxis.user(ctx.user_id)
        by_ws_route = await self._logs.aggregate_by_route_names_by_axis(
            ws_axis, page_route_names, start, end
        )
        by_user_route = await self._logs.aggregate_by_route_names_by_axis(
            u_axis, page_route_names, start, end
        )
        by_ws_dep = await self._logs.aggregate_by_deployment_ids_by_axis(
            ws_axis, model_ids, start, end
        )
        by_user_dep = await self._logs.aggregate_by_deployment_ids_by_axis(
            u_axis, model_ids, start, end
        )
        items: list[dict[str, Any]] = []
        for m in models_page:
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
        return items, total, start, end


__all__ = ["GatewayUsageLogReadMixin"]
