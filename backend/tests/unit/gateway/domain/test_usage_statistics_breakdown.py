"""usage_statistics_breakdown 域规则单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.usage_read_model import (
    UsageStatisticsBreakdownBy,
    UsageStatisticsGroupBy,
)
from domains.gateway.domain.usage_statistics_breakdown import (
    breakdown_by_to_group_by,
    normalize_usage_statistics_parent_group_key,
)
from libs.exceptions import ValidationError


def test_breakdown_by_to_group_by_maps_credential_and_model() -> None:
    assert breakdown_by_to_group_by(UsageStatisticsBreakdownBy.CREDENTIAL) == (
        UsageStatisticsGroupBy.CREDENTIAL
    )
    assert breakdown_by_to_group_by(UsageStatisticsBreakdownBy.MODEL) == (
        UsageStatisticsGroupBy.MODEL
    )


def test_normalize_parent_key_accepts_valid_uuid() -> None:
    uid = uuid.uuid4()
    assert (
        normalize_usage_statistics_parent_group_key(
            UsageStatisticsGroupBy.USER,
            str(uid),
        )
        == str(uid)
    )


def test_normalize_parent_key_rejects_invalid_uuid() -> None:
    with pytest.raises(ValidationError, match="invalid parent_group_key"):
        normalize_usage_statistics_parent_group_key(
            UsageStatisticsGroupBy.USER,
            "not-a-uuid",
        )


def test_normalize_parent_key_allows_empty_for_unassociated() -> None:
    assert (
        normalize_usage_statistics_parent_group_key(
            UsageStatisticsGroupBy.USER,
            "  ",
        )
        == ""
    )


def test_normalize_parent_key_model_is_opaque_string() -> None:
    assert (
        normalize_usage_statistics_parent_group_key(
            UsageStatisticsGroupBy.MODEL,
            "my-route",
        )
        == "my-route"
    )
