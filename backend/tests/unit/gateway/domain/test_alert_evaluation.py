"""alert_evaluation 纯函数单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

from domains.gateway.domain.alert_metric_aggregates import AlertMetricAggregates
from domains.gateway.domain.alert_rule_snapshot import AlertRuleSnapshot
from domains.gateway.domain.policies.alert_evaluation import (
    alert_cooldown_elapsed,
    evaluate_alert_rule,
    evaluate_error_rate,
    evaluate_request_rate,
)


def test_alert_cooldown_elapsed_when_never_triggered() -> None:
    now = datetime.now(UTC)
    assert alert_cooldown_elapsed(None, now) is True


def test_alert_cooldown_not_elapsed_within_window() -> None:
    now = datetime.now(UTC)
    last = now - timedelta(seconds=60)
    assert alert_cooldown_elapsed(last, now, cooldown_seconds=300) is False


def test_evaluate_error_rate_insufficient_data() -> None:
    assert evaluate_error_rate(threshold=0.5, total_count=0, error_count=0) is None


def test_evaluate_error_rate_triggers() -> None:
    result = evaluate_error_rate(threshold=0.1, total_count=10, error_count=5)
    assert result is not None
    assert result.triggered is True
    assert result.value == 0.5


def test_evaluate_request_rate() -> None:
    result = evaluate_request_rate(threshold=1.0, request_count=10, window_minutes=5)
    assert result.triggered is True
    assert result.value == 2.0


def test_evaluate_alert_rule_dispatches_error_rate() -> None:
    snapshot = AlertRuleSnapshot(
        rule_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        is_system=False,
        name="r",
        metric="error_rate",
        threshold=Decimal("0.1"),
        window_minutes=5,
        channels={},
        last_triggered_at=None,
    )
    aggregates = AlertMetricAggregates(
        metric="error_rate",
        total_count=10,
        error_count=5,
        window_minutes=5,
    )
    result = evaluate_alert_rule(snapshot, aggregates)
    assert result is not None
    assert result.triggered is True
