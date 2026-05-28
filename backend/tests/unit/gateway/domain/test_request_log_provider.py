"""``resolve_request_log_provider`` / hint 推断 — domain 纯函数单测。"""

from __future__ import annotations

from domains.gateway.domain.request_log_provider import (
    infer_provider_from_model_hint,
    infer_provider_from_model_hints,
    resolve_request_log_provider,
)


def test_infer_provider_from_model_hint_skips_router_encoded() -> None:
    assert (
        infer_provider_from_model_hint("gw/t/00000000-0000-0000-0000-000000000001/my-virtual")
        is None
    )


def test_infer_provider_from_model_hint_infers_doubao() -> None:
    assert infer_provider_from_model_hint("doubao-seedance-2-0-260128") == "volcengine"


def test_infer_provider_from_model_hints_returns_first_match() -> None:
    assert (
        infer_provider_from_model_hints(
            "gw/t/00000000-0000-0000-0000-000000000001/my-virtual",
            "doubao-seedance-2-0-260128",
        )
        == "volcengine"
    )


def test_resolve_prefers_metadata_provider() -> None:
    assert resolve_request_log_provider(metadata_provider="anthropic") == "anthropic"


def test_resolve_falls_back_to_model_info_provider() -> None:
    assert resolve_request_log_provider(model_info_provider="deepseek") == "deepseek"


def test_resolve_infers_from_upstream_model() -> None:
    assert resolve_request_log_provider(upstream_model="volcengine/doubao-pro-32k") == "volcengine"


def test_resolve_infers_from_response_model() -> None:
    assert resolve_request_log_provider(response_model="dashscope/qwen-max") == "dashscope"


def test_resolve_infers_from_model_hints() -> None:
    assert resolve_request_log_provider(model_hints=("doubao-seedance-2-0-260128",)) == "volcengine"
