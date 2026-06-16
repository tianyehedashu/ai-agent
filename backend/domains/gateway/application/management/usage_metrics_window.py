"""Hybrid 读路径时间窗切分。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class UsageMetricsWindowSplit:
    """将 [start, end] 按热尾水位切为冷段（hourly）与热段（logs）。"""

    cold_start: datetime | None
    cold_end_exclusive: datetime | None
    hot_start: datetime | None
    hot_end: datetime | None


def floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def compute_hot_cutoff(*, now: datetime | None = None, hot_tail_hours: int) -> datetime:
    when = (now or datetime.now(UTC)).astimezone(UTC)
    return floor_hour(when) - timedelta(hours=hot_tail_hours)


def split_usage_metrics_window(
    start: datetime,
    end: datetime,
    *,
    hot_cutoff: datetime,
) -> UsageMetricsWindowSplit:
    """``start``/``end`` 含端；冷段为 ``[cold_start, cold_end_exclusive)``，热段为 ``[hot_start, hot_end]``。"""
    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    cutoff = hot_cutoff.astimezone(UTC)

    if end_utc < cutoff:
        return UsageMetricsWindowSplit(
            cold_start=start_utc,
            cold_end_exclusive=end_utc + timedelta(microseconds=1),
            hot_start=None,
            hot_end=None,
        )
    if start_utc >= cutoff:
        return UsageMetricsWindowSplit(
            cold_start=None,
            cold_end_exclusive=None,
            hot_start=start_utc,
            hot_end=end_utc,
        )
    return UsageMetricsWindowSplit(
        cold_start=start_utc,
        cold_end_exclusive=cutoff,
        hot_start=cutoff,
        hot_end=end_utc,
    )


def hourly_bucket_range(
    start: datetime,
    end_exclusive: datetime,
) -> tuple[datetime, datetime]:
    """hourly 表 ``bucket_at`` 查询范围 ``[bucket_start, bucket_end_exclusive)``。"""
    return floor_hour(start), floor_hour(end_exclusive)


def cold_logs_time_range(
    split: UsageMetricsWindowSplit,
) -> tuple[datetime, datetime] | None:
    """冷段在明细表上的闭区间 ``[start, end]``（与 ``RequestLogRepository`` 时间谓词对齐）。"""
    if split.cold_start is None or split.cold_end_exclusive is None:
        return None
    cold_end_inclusive = split.cold_end_exclusive - timedelta(microseconds=1)
    if split.cold_start > cold_end_inclusive:
        return None
    return split.cold_start, cold_end_inclusive


__all__ = [
    "UsageMetricsWindowSplit",
    "cold_logs_time_range",
    "compute_hot_cutoff",
    "floor_hour",
    "hourly_bucket_range",
    "split_usage_metrics_window",
]
