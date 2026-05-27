"""团队邀请候选人可见范围策略。"""

from __future__ import annotations

import pytest

from domains.tenancy.domain.policies.team_invite_candidate_scope import (
    parse_invite_candidate_scope,
    validate_invite_candidate_scope_value,
)


def test_parse_defaults_to_all_users() -> None:
    assert parse_invite_candidate_scope(None) == "all_users"
    assert parse_invite_candidate_scope({}) == "all_users"


def test_parse_shared_teams() -> None:
    assert parse_invite_candidate_scope({"invite_candidate_scope": "shared_teams"}) == (
        "shared_teams"
    )


def test_validate_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invite_candidate_scope"):
        validate_invite_candidate_scope_value("enterprise")
