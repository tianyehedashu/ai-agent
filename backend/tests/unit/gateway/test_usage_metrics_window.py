"""usage_metrics_window 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domains.gateway.application.usage.management.usage_metrics_window import (
    cold_logs_time_range,
    compute_hot_cutoff,
    split_usage_metrics_window,
)


@pytest.mark.unit
def test_split_all_cold() -> None:
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
    hot = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    split = split_usage_metrics_window(start, end, hot_cutoff=hot)
    assert split.hot_start is None
    assert split.cold_start == start


@pytest.mark.unit
def test_split_all_hot() -> None:
    start = datetime(2026, 6, 10, 1, 0, tzinfo=UTC)
    end = datetime(2026, 6, 10, 3, 0, tzinfo=UTC)
    hot = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    split = split_usage_metrics_window(start, end, hot_cutoff=hot)
    assert split.cold_start is None
    assert split.hot_start == start


@pytest.mark.unit
def test_split_hybrid() -> None:
    now = datetime(2026, 6, 10, 15, 30, tzinfo=UTC)
    hot = compute_hot_cutoff(now=now, hot_tail_hours=2)
    start = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    end = now
    split = split_usage_metrics_window(start, end, hot_cutoff=hot)
    assert split.cold_start == start
    assert split.hot_start == hot
    assert split.hot_end == end


@pytest.mark.unit
def test_cold_logs_time_range_all_cold() -> None:
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
    split = split_usage_metrics_window(
        start,
        end,
        hot_cutoff=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
    )
    cold = cold_logs_time_range(split)
    assert cold == (start, end)


@pytest.mark.unit
def test_cold_logs_time_range_hybrid_excludes_hot_boundary() -> None:
    cutoff = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    split = split_usage_metrics_window(
        datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        datetime(2026, 6, 10, 15, 0, tzinfo=UTC),
        hot_cutoff=cutoff,
    )
    cold = cold_logs_time_range(split)
    assert cold is not None
    assert cold[1] < cutoff
