"""Dashboard/Statistics hybrid 读路由（hourly 冷段 + logs 热尾）。"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.application.management.usage_metrics import (
    merge_statistics_items,
    merge_statistics_totals,
    merge_summary_slices,
)
from domains.gateway.application.management.usage_metrics_window import (
    UsageMetricsWindowSplit,
    cold_logs_time_range,
    compute_hot_cutoff,
    hourly_bucket_range,
    split_usage_metrics_window,
)
from domains.gateway.domain.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
    UsageStatisticsParentScope,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    BreakdownPairRow,
    RequestLogUsageAggregateRow,
    RequestLogUsageTotals,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from domains.gateway.domain.usage_axis import UsageAxis
    from domains.gateway.infrastructure.repositories.metrics_hourly_read_repository import (
        MetricsHourlyReadRepository,
    )
    from domains.gateway.infrastructure.repositories.request_log_repository import (
        RequestLogRepository,
    )

_EMPTY_TOTALS = RequestLogUsageTotals(0, 0, 0, 0, 0, 0, 0, Decimal("0"), 0.0, 0.0, 0)


class UsageMetricsRouter:
    def __init__(
        self,
        logs: RequestLogRepository,
        hourly: MetricsHourlyReadRepository,
    ) -> None:
        self._logs = logs
        self._hourly = hourly

    def _hybrid_enabled(self) -> bool:
        return settings.gateway_metrics_hybrid_read_enabled

    @staticmethod
    def _hourly_supported_for_axis(axis: UsageAxis) -> bool:
        """hourly 轴与 logs 语义对齐的场景才走冷段；其余整窗 fallback 明细。"""
        if axis.is_user():
            return False
        return not (axis.is_workspace() and axis.member_user_id is not None)

    def _hourly_supported_for_statistics(
        self,
        *,
        axis: UsageAxis,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        status_filter: str | None = None,
        parent_group_by: UsageStatisticsGroupBy | None = None,
    ) -> bool:
        if not self._hourly_supported_for_axis(axis):
            return False
        if status_filter is not None or filters.status is not None:
            return False
        for candidate in (group_by, parent_group_by):
            if candidate in (
                UsageStatisticsGroupBy.STATUS,
                UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL,
                UsageStatisticsGroupBy.RESOURCE_OWNER,
            ):
                return False
        return True

    @staticmethod
    def _cold_bucket_range(split: UsageMetricsWindowSplit) -> tuple[datetime, datetime] | None:
        if split.cold_start is None or split.cold_end_exclusive is None:
            return None
        bucket_start, bucket_end = hourly_bucket_range(
            split.cold_start,
            split.cold_end_exclusive,
        )
        if bucket_start >= bucket_end:
            return None
        return bucket_start, bucket_end

    async def _attach_cold_client_type(
        self,
        axis: UsageAxis,
        split: UsageMetricsWindowSplit,
        summary: dict[str, Any],
        list_kwargs: dict[str, Any],
    ) -> None:
        cold_logs = cold_logs_time_range(split)
        if cold_logs is None:
            summary["by_client_type"] = []
            return
        summary["by_client_type"] = await self._logs.aggregate_by_client_type(
            axis,
            cold_logs[0],
            cold_logs[1],
            **list_kwargs,
        )

    async def _logs_summary_with_client_type(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        list_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        summary = await self._logs.aggregate_summary_by_axis(axis, start, end, **list_kwargs)
        summary["by_client_type"] = await self._logs.aggregate_by_client_type(
            axis, start, end, **list_kwargs
        )
        return summary

    async def aggregate_summary(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        status_filter: str | None = None,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
        client_type: str | None = None,
    ) -> dict[str, Any]:
        filters = UsageStatisticsFilters(
            credential_id=credential_id,
            user_id=user_id,
            model=model,
            capability=capability,
            status=status_filter,
            vkey_id=vkey_id,
            client_type=client_type,
        )
        list_kwargs = {
            "status": filters.status,
            "capability": filters.capability,
            "vkey_id": filters.vkey_id,
            "credential_id": filters.credential_id,
            "user_id": filters.user_id,
            "model": filters.model,
            "client_type": filters.client_type,
        }
        # client_type 过滤暂不支持小时级 rollup，直接走明细
        if (
            not self._hybrid_enabled()
            or filters.status is not None
            or filters.client_type is not None
            or not self._hourly_supported_for_axis(axis)
        ):
            return await self._logs_summary_with_client_type(axis, start, end, list_kwargs)

        split = split_usage_metrics_window(
            start,
            end,
            hot_cutoff=compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours),
        )
        cold_range = self._cold_bucket_range(split)
        has_hot = split.hot_start is not None and split.hot_end is not None

        if cold_range is not None and not has_hot:
            bucket_start, bucket_end = cold_range
            merged = await self._hourly.aggregate_summary_by_axis(
                axis,
                bucket_start,
                bucket_end,
                capability=filters.capability,
                vkey_id=filters.vkey_id,
                credential_id=filters.credential_id,
                user_id=filters.user_id,
                model=filters.model,
            )
            await self._attach_cold_client_type(axis, split, merged, list_kwargs)
            return merged

        if has_hot and cold_range is None:
            return await self._logs_summary_with_client_type(
                axis, split.hot_start, split.hot_end, list_kwargs
            )

        if cold_range is None and not has_hot:
            return await self._logs_summary_with_client_type(axis, start, end, list_kwargs)

        assert cold_range is not None
        bucket_start, bucket_end = cold_range
        merged: dict[str, Any] | None = await self._hourly.aggregate_summary_by_axis(
            axis,
            bucket_start,
            bucket_end,
            capability=filters.capability,
            vkey_id=filters.vkey_id,
            credential_id=filters.credential_id,
            user_id=filters.user_id,
            model=filters.model,
        )
        hot_summary = await self._logs_summary_with_client_type(
            axis, split.hot_start, split.hot_end, list_kwargs
        )
        merged = merge_summary_slices(merged, hot_summary)
        if "by_client_type" not in merged:
            merged["by_client_type"] = hot_summary.get("by_client_type", [])
        return merged

    async def _aggregate_statistics_cross_boundary(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        cold_range: tuple[datetime, datetime],
        split: UsageMetricsWindowSplit,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        page: int,
        page_size: int,
        parent_scope: UsageStatisticsParentScope | None,
    ) -> tuple[list[RequestLogUsageAggregateRow], RequestLogUsageTotals, int]:
        bucket_start, bucket_end = cold_range
        hot_start = split.hot_start
        hot_end = split.hot_end
        assert hot_start is not None and hot_end is not None

        _, cold_totals, cold_group_total = await self._hourly.aggregate_usage_statistics_by_axis(
            axis,
            bucket_start,
            bucket_end,
            group_by=group_by,
            filters=filters,
            page=1,
            page_size=0,
            parent_scope=parent_scope,
        )
        _, hot_totals, hot_group_total = await self._logs.aggregate_usage_statistics_by_axis(
            axis,
            hot_start,
            hot_end,
            group_by=group_by,
            filters=filters,
            page=1,
            page_size=0,
            parent_scope=parent_scope,
        )
        if cold_group_total + hot_group_total > settings.gateway_metrics_hybrid_merge_max_groups:
            return await self._logs.aggregate_usage_statistics_by_axis(
                axis,
                start,
                end,
                group_by=group_by,
                filters=filters,
                page=page,
                page_size=page_size,
                parent_scope=parent_scope,
            )

        cold_items, cold_totals, _ = await self._hourly.aggregate_usage_statistics_by_axis(
            axis,
            bucket_start,
            bucket_end,
            group_by=group_by,
            filters=filters,
            parent_scope=parent_scope,
            fetch_all_groups=True,
        )
        hot_items, hot_totals, _ = await self._logs.aggregate_usage_statistics_by_axis(
            axis,
            hot_start,
            hot_end,
            group_by=group_by,
            filters=filters,
            parent_scope=parent_scope,
            fetch_all_groups=True,
        )

        merged_items = merge_statistics_items(cold_items, hot_items)
        merged_group_total = len(merged_items)
        offset = max(0, (page - 1) * page_size)
        page_items = merged_items[offset : offset + page_size]

        totals_dict = merge_statistics_totals(
            cold_totals or _EMPTY_TOTALS,
            hot_totals or _EMPTY_TOTALS,
        )
        totals = RequestLogUsageTotals(
            requests=int(totals_dict["requests"]),
            success_count=int(totals_dict["success_count"]),
            failure_count=int(totals_dict["failure_count"]),
            input_tokens=int(totals_dict["input_tokens"]),
            output_tokens=int(totals_dict["output_tokens"]),
            cached_tokens=int(totals_dict["cached_tokens"]),
            cache_creation_tokens=int(totals_dict["cache_creation_tokens"]),
            cost_usd=totals_dict["cost_usd"]
            if isinstance(totals_dict["cost_usd"], Decimal)
            else Decimal("0"),
            avg_latency_ms=float(totals_dict["avg_latency_ms"]),
            avg_ttfb_ms=float(totals_dict["avg_ttfb_ms"]),
            cache_hit_count=int(totals_dict["cache_hit_count"]),
        )
        return page_items, totals, merged_group_total

    async def aggregate_usage_statistics(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        page: int,
        page_size: int,
        parent_scope: UsageStatisticsParentScope | None = None,
    ) -> tuple[list[RequestLogUsageAggregateRow], RequestLogUsageTotals, int]:
        if not self._hybrid_enabled() or not self._hourly_supported_for_statistics(
            axis=axis,
            group_by=group_by,
            filters=filters,
            parent_group_by=parent_scope.group_by if parent_scope else None,
        ):
            return await self._logs.aggregate_usage_statistics_by_axis(
                axis,
                start,
                end,
                group_by=group_by,
                filters=filters,
                page=page,
                page_size=page_size,
                parent_scope=parent_scope,
            )

        split = split_usage_metrics_window(
            start,
            end,
            hot_cutoff=compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours),
        )
        cold_range = self._cold_bucket_range(split)
        has_hot = split.hot_start is not None and split.hot_end is not None

        if cold_range is not None and not has_hot:
            bucket_start, bucket_end = cold_range
            return await self._hourly.aggregate_usage_statistics_by_axis(
                axis,
                bucket_start,
                bucket_end,
                group_by=group_by,
                filters=filters,
                page=page,
                page_size=page_size,
                parent_scope=parent_scope,
            )

        if has_hot and cold_range is None:
            return await self._logs.aggregate_usage_statistics_by_axis(
                axis,
                split.hot_start,
                split.hot_end,
                group_by=group_by,
                filters=filters,
                page=page,
                page_size=page_size,
                parent_scope=parent_scope,
            )

        if cold_range is None and not has_hot:
            return await self._logs.aggregate_usage_statistics_by_axis(
                axis,
                start,
                end,
                group_by=group_by,
                filters=filters,
                page=page,
                page_size=page_size,
                parent_scope=parent_scope,
            )

        return await self._aggregate_statistics_cross_boundary(
            axis,
            start,
            end,
            cold_range=cold_range,
            split=split,
            group_by=group_by,
            filters=filters,
            page=page,
            page_size=page_size,
            parent_scope=parent_scope,
        )

    async def count_usage_requests(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        filters: UsageStatisticsFilters,
        parent_scope: UsageStatisticsParentScope | None = None,
    ) -> int:
        if not self._hybrid_enabled() or not self._hourly_supported_for_statistics(
            axis=axis,
            group_by=UsageStatisticsGroupBy.MODEL,
            filters=filters,
            parent_group_by=parent_scope.group_by if parent_scope else None,
        ):
            return await self._logs.count_usage_requests_by_axis(
                axis,
                start,
                end,
                filters=filters,
                parent_scope=parent_scope,
            )

        split = split_usage_metrics_window(
            start,
            end,
            hot_cutoff=compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours),
        )
        cold_range = self._cold_bucket_range(split)
        has_hot = split.hot_start is not None and split.hot_end is not None
        total = 0
        if cold_range is not None:
            total += await self._hourly.count_usage_requests_by_axis(
                axis,
                cold_range[0],
                cold_range[1],
                filters=filters,
                parent_scope=parent_scope,
            )
        if has_hot:
            total += await self._logs.count_usage_requests_by_axis(
                axis,
                split.hot_start,
                split.hot_end,
                filters=filters,
                parent_scope=parent_scope,
            )
        return total

    @staticmethod
    def _merge_breakdown_pairs(
        cold: list[BreakdownPairRow],
        hot: list[BreakdownPairRow],
    ) -> list[BreakdownPairRow]:
        """按 ``(父键, 二次键)`` 合并冷热请求数；二次键原值与快照取非空者。"""
        index: dict[tuple[str, str], BreakdownPairRow] = {}
        order: list[tuple[str, str]] = []
        for row in (*cold, *hot):
            bk_str = "" if row.breakdown_key is None else str(row.breakdown_key)
            key = (row.parent_key, bk_str)
            existing = index.get(key)
            if existing is None:
                index[key] = row
                order.append(key)
                continue
            index[key] = BreakdownPairRow(
                parent_key=row.parent_key,
                breakdown_key=existing.breakdown_key
                if existing.breakdown_key is not None
                else row.breakdown_key,
                label_snapshot=existing.label_snapshot or row.label_snapshot,
                requests=existing.requests + row.requests,
            )
        return [index[key] for key in order]

    async def aggregate_breakdown_pairs(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        parent_group_by: UsageStatisticsGroupBy,
        breakdown_group_by: UsageStatisticsGroupBy,
        parent_keys: list[str],
        filters: UsageStatisticsFilters,
    ) -> list[BreakdownPairRow]:
        """批量 breakdown：一次拿回本页所有父行的二次分组分布（冷热合并）。"""
        if not parent_keys:
            return []
        if not self._hybrid_enabled() or not self._hourly_supported_for_statistics(
            axis=axis,
            group_by=breakdown_group_by,
            filters=filters,
            parent_group_by=parent_group_by,
        ):
            return await self._logs.aggregate_breakdown_pairs_by_axis(
                axis,
                start,
                end,
                parent_group_by=parent_group_by,
                breakdown_group_by=breakdown_group_by,
                parent_keys=parent_keys,
                filters=filters,
            )

        split = split_usage_metrics_window(
            start,
            end,
            hot_cutoff=compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours),
        )
        cold_range = self._cold_bucket_range(split)
        has_hot = split.hot_start is not None and split.hot_end is not None

        cold_pairs: list[BreakdownPairRow] = []
        if cold_range is not None:
            cold_pairs = await self._hourly.aggregate_breakdown_pairs_by_axis(
                axis,
                cold_range[0],
                cold_range[1],
                parent_group_by=parent_group_by,
                breakdown_group_by=breakdown_group_by,
                parent_keys=parent_keys,
                filters=filters,
            )
        hot_pairs: list[BreakdownPairRow] = []
        if has_hot:
            hot_pairs = await self._logs.aggregate_breakdown_pairs_by_axis(
                axis,
                split.hot_start,
                split.hot_end,
                parent_group_by=parent_group_by,
                breakdown_group_by=breakdown_group_by,
                parent_keys=parent_keys,
                filters=filters,
            )
        if cold_range is None and not has_hot:
            return await self._logs.aggregate_breakdown_pairs_by_axis(
                axis,
                start,
                end,
                parent_group_by=parent_group_by,
                breakdown_group_by=breakdown_group_by,
                parent_keys=parent_keys,
                filters=filters,
            )
        if len(cold_pairs) + len(hot_pairs) > settings.gateway_metrics_hybrid_merge_max_groups:
            return await self._logs.aggregate_breakdown_pairs_by_axis(
                axis,
                start,
                end,
                parent_group_by=parent_group_by,
                breakdown_group_by=breakdown_group_by,
                parent_keys=parent_keys,
                filters=filters,
            )
        return self._merge_breakdown_pairs(cold_pairs, hot_pairs)


__all__ = ["UsageMetricsRouter"]
