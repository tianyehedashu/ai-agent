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
    validate_breakdown_batch_parent_keys,
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
    assert normalize_usage_statistics_parent_group_key(
        UsageStatisticsGroupBy.USER,
        str(uid),
    ) == str(uid)


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


def test_validate_breakdown_batch_parent_keys_rejects_over_limit() -> None:
    with pytest.raises(ValidationError, match="parent_group_keys exceeds maximum"):
        validate_breakdown_batch_parent_keys(["k"] * 201)


def test_validate_breakdown_batch_parent_keys_accepts_at_limit() -> None:
    validate_breakdown_batch_parent_keys(["k"] * 200)
