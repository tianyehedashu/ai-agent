"""Coding Agent User-Agent 注入策略。"""

from domains.gateway.domain.coding_agent_ua import (
    apply_coding_agent_ua_litellm_params,
    resolve_coding_agent_ua,
)


def test_resolve_coding_agent_ua_for_moonshot_coding_plan() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id="moonshot.coding_plan",
            provider="moonshot",
        )
        == "claude-code/1.0"
    )


def test_resolve_coding_agent_ua_absent_for_default_profile() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id="moonshot.default",
            provider="moonshot",
        )
        is None
    )


def test_apply_coding_agent_ua_litellm_params_merges_headers() -> None:
    params = apply_coding_agent_ua_litellm_params(
        {"model": "kimi-for-coding"},
        credential_profile_id="moonshot.coding_plan",
        provider="moonshot",
    )
    assert params["extra_headers"]["User-Agent"] == "claude-code/1.0"
