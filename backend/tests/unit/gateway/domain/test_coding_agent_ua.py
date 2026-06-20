"""Coding Agent User-Agent 注入策略。"""

from domains.gateway.domain.coding_agent_ua import (
    apply_coding_agent_ua_litellm_params,
    resolve_coding_agent_ua,
)


class _FakeCredential:
    def __init__(self, *, api_base: str | None = None, api_bases: dict | None = None) -> None:
        self.api_base = api_base
        self.api_bases = api_bases


def test_resolve_coding_agent_ua_for_moonshot_coding_plan() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id="moonshot.coding_plan",
            provider="moonshot",
        )
        == "claude-code/1.0.0"
    )


def test_resolve_coding_agent_ua_absent_for_default_profile() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id="moonshot.default",
            provider="moonshot",
        )
        is None
    )


def test_resolve_coding_agent_ua_infers_from_credential_api_base() -> None:
    """profile_id 为 default 但 api_base 命中 Coding endpoint，应回退注入 UA。"""
    assert (
        resolve_coding_agent_ua(
            credential_profile_id="moonshot.default",
            provider="moonshot",
            credential=_FakeCredential(api_base="https://api.kimi.com/coding/v1"),
        )
        == "claude-code/1.0.0"
    )


def test_resolve_coding_agent_ua_infers_from_api_bases_json() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id=None,
            provider="moonshot",
            credential=_FakeCredential(
                api_bases={"openai_compat": "https://api.kimi.com/coding/v1"}
            ),
        )
        == "claude-code/1.0.0"
    )


def test_resolve_coding_agent_ua_fallback_by_real_model() -> None:
    """无 profile 且无 api_base 覆盖时，按真实模型名兜底。"""
    assert (
        resolve_coding_agent_ua(
            credential_profile_id=None,
            provider="moonshot",
            credential=_FakeCredential(),
            real_model="kimi-for-coding",
        )
        == "claude-code/1.0.0"
    )


def test_resolve_coding_agent_ua_no_fallback_for_non_coding_model() -> None:
    assert (
        resolve_coding_agent_ua(
            credential_profile_id=None,
            provider="moonshot",
            credential=_FakeCredential(),
            real_model="moonshot-v1-8k",
        )
        is None
    )


def test_apply_coding_agent_ua_litellm_params_merges_headers() -> None:
    params = apply_coding_agent_ua_litellm_params(
        {"model": "kimi-for-coding"},
        credential_profile_id="moonshot.coding_plan",
        provider="moonshot",
    )
    assert params["extra_headers"]["User-Agent"] == "claude-code/1.0.0"
