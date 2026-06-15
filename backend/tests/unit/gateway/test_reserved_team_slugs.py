"""reserved_team_slugs 单测。"""

from __future__ import annotations

import pytest

from domains.tenancy.domain.policies.reserved_team_slugs import (
    RESERVED_TEAM_SLUGS,
    assert_slug_not_reserved,
)


@pytest.mark.unit
def test_reserved_slugs_include_major_providers() -> None:
    assert "openai" in RESERVED_TEAM_SLUGS
    assert "anthropic" in RESERVED_TEAM_SLUGS
    assert "deepseek" in RESERVED_TEAM_SLUGS


@pytest.mark.unit
def test_assert_slug_not_reserved_rejects_openai() -> None:
    with pytest.raises(ValueError, match="reserved"):
        assert_slug_not_reserved("openai")


@pytest.mark.unit
def test_assert_slug_not_reserved_allows_custom_slug() -> None:
    assert_slug_not_reserved("my-data-team")
