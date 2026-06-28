"""配额行「启用停用 + 起止时间」执法判定纯函数测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domains.gateway.domain.quota.quota_window_enforcement import (
    is_quota_row_enforceable,
)

_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def test_enabled_no_window_is_enforceable() -> None:
    assert is_quota_row_enforceable(
        enabled=True, valid_from=None, valid_until=None, now=_NOW
    )


def test_disabled_is_never_enforceable() -> None:
    assert not is_quota_row_enforceable(
        enabled=False, valid_from=None, valid_until=None, now=_NOW
    )


def test_before_valid_from_is_skipped() -> None:
    assert not is_quota_row_enforceable(
        enabled=True,
        valid_from=_NOW + timedelta(hours=1),
        valid_until=None,
        now=_NOW,
    )


def test_at_or_after_valid_until_is_skipped() -> None:
    # valid_until 不含：now == valid_until 即已失效。
    assert not is_quota_row_enforceable(
        enabled=True, valid_from=None, valid_until=_NOW, now=_NOW
    )
    assert not is_quota_row_enforceable(
        enabled=True,
        valid_from=None,
        valid_until=_NOW - timedelta(seconds=1),
        now=_NOW,
    )


@pytest.mark.parametrize(
    ("valid_from", "valid_until"),
    [
        (_NOW - timedelta(hours=1), _NOW + timedelta(hours=1)),
        (_NOW, _NOW + timedelta(hours=1)),  # valid_from 含：now == valid_from 生效
        (_NOW - timedelta(days=1), None),
        (None, _NOW + timedelta(days=1)),
    ],
)
def test_within_window_is_enforceable(
    valid_from: datetime | None, valid_until: datetime | None
) -> None:
    assert is_quota_row_enforceable(
        enabled=True, valid_from=valid_from, valid_until=valid_until, now=_NOW
    )
