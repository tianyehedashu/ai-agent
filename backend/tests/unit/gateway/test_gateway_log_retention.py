"""gateway 请求日志分区保留辅助逻辑单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domains.gateway.infrastructure.jobs.sql_jobs_repository import (
    _PARTITION_NAME_RE as _PARTITION_NAME,
)
from domains.gateway.infrastructure.jobs.sql_jobs_repository import (
    month_partition_upper_bound as _month_partition_upper_bound,
)


@pytest.mark.unit
class TestMonthPartitionUpperBound:
    def test_january(self) -> None:
        upper = _month_partition_upper_bound(2025, 1)
        assert upper == datetime(2025, 2, 1, tzinfo=UTC)

    def test_december(self) -> None:
        upper = _month_partition_upper_bound(2025, 12)
        assert upper == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.unit
class TestPartitionNameRegex:
    def test_matches_expected_tables(self) -> None:
        assert _PARTITION_NAME.match("gateway_request_logs_y2025m03")
        assert _PARTITION_NAME.match("gateway_request_logs_y2024m12")

    def test_rejects_other_names(self) -> None:
        assert _PARTITION_NAME.match("gateway_request_logs") is None
        assert _PARTITION_NAME.match("other_y2025m01") is None


@pytest.mark.unit
class TestRetentionCutoffSemantics:
    """整月分区上界 <= cutoff 时可删：与 _drop_expired 中条件一致。"""

    def test_february_kept_when_cutoff_before_march(self) -> None:
        now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        retention_days = 30
        cutoff = now - timedelta(days=retention_days)
        upper_feb = _month_partition_upper_bound(2026, 2)
        assert upper_feb == datetime(2026, 3, 1, tzinfo=UTC)
        assert not upper_feb <= cutoff

    def test_february_dropped_when_cutoff_after_march_first(self) -> None:
        now = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
        retention_days = 30
        cutoff = now - timedelta(days=retention_days)
        upper_feb = _month_partition_upper_bound(2026, 2)
        assert upper_feb <= cutoff
