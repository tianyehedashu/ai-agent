"""Tests for plan quota merge helper."""

from decimal import Decimal

from domains.gateway.application.quota.management.plan_quota_merge import merge_plan_quotas_by_label


class _QuotaRow:
    def __init__(
        self,
        label: str,
        *,
        limit_usd: Decimal | None = None,
        unit_price_usd_per_token: Decimal | None = None,
    ) -> None:
        self.label = label
        self.window_seconds = 3600
        self.reset_strategy = "rolling"
        self.limit_usd = limit_usd
        self.limit_tokens = None
        self.limit_requests = None
        self.unit_price_usd_per_token = unit_price_usd_per_token
        self.unit_price_usd_per_request = None


def test_merge_replaces_matching_label() -> None:
    existing = [_QuotaRow("default", limit_usd=Decimal("10"))]
    payload = {
        "label": "default",
        "window_seconds": 86400,
        "reset_strategy": "rolling",
        "limit_usd": Decimal("20"),
        "limit_tokens": None,
        "limit_requests": None,
    }
    merged = merge_plan_quotas_by_label(existing, "default", payload)
    assert len(merged) == 1
    assert merged[0]["limit_usd"] == Decimal("20")
    assert merged[0]["window_seconds"] == 86400


def test_merge_preserves_other_labels() -> None:
    existing = [_QuotaRow("weekly"), _QuotaRow("default")]
    payload = {
        "label": "default",
        "window_seconds": 0,
        "reset_strategy": "rolling",
        "limit_usd": Decimal("5"),
        "limit_tokens": None,
        "limit_requests": None,
    }
    merged = merge_plan_quotas_by_label(existing, "default", payload)
    assert len(merged) == 2
    assert merged[0]["label"] == "weekly"
    assert merged[1]["label"] == "default"


def test_merge_preserves_extra_fields() -> None:
    existing = [_QuotaRow("default", unit_price_usd_per_token=Decimal("0.001"))]
    payload = {
        "label": "default",
        "window_seconds": 0,
        "reset_strategy": "rolling",
        "limit_usd": None,
        "limit_tokens": None,
        "limit_requests": None,
        "unit_price_usd_per_token": Decimal("0.002"),
    }
    merged = merge_plan_quotas_by_label(
        existing,
        "other",
        payload,
        extra_fields=("unit_price_usd_per_token", "unit_price_usd_per_request"),
    )
    assert len(merged) == 2
    assert merged[0]["unit_price_usd_per_token"] == Decimal("0.001")
    assert merged[1]["unit_price_usd_per_token"] == Decimal("0.002")
