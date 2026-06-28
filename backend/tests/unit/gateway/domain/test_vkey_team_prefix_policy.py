"""vkey_team_prefix_policy 纯函数单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.errors import VkeyTeamPrefixUnknownError
from domains.gateway.domain.vkey.virtual_key_team_prefix_policy import resolve_vkey_model_prefix


def test_no_prefix_falls_to_bound_team() -> None:
    team_id = uuid.uuid4()
    out = resolve_vkey_model_prefix(
        bound_team_id=team_id,
        raw_model="gpt-4o",
        slug_map={},
        strict=False,
    )
    assert out.effective_team_id == team_id
    assert out.real_model_name == "gpt-4o"
    assert out.matched_slug is None


def test_slug_hit_in_grants() -> None:
    primary = uuid.uuid4()
    shared = uuid.uuid4()
    out = resolve_vkey_model_prefix(
        bound_team_id=primary,
        raw_model="my-team/gpt-4o",
        slug_map={"my-team": shared},
        strict=False,
    )
    assert out.effective_team_id == shared
    assert out.real_model_name == "gpt-4o"
    assert out.matched_slug == "my-team"


def test_vendor_prefix_not_in_grants_falls_to_bound() -> None:
    team_id = uuid.uuid4()
    out = resolve_vkey_model_prefix(
        bound_team_id=team_id,
        raw_model="openai/gpt-4o",
        slug_map={},
        strict=False,
    )
    assert out.effective_team_id == team_id
    assert out.real_model_name == "openai/gpt-4o"
    assert out.matched_slug is None


def test_strict_unknown_slug_raises() -> None:
    with pytest.raises(VkeyTeamPrefixUnknownError):
        resolve_vkey_model_prefix(
            bound_team_id=uuid.uuid4(),
            raw_model="unknown/gpt-4o",
            slug_map={"other": uuid.uuid4()},
            strict=True,
        )
