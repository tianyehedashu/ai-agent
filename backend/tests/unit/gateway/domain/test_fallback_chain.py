"""``fallback_chain`` —— 虚拟路由主模型失败后的 fallback 链路还原。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from domains.gateway.domain.fallback_chain import (
    attempted_fallbacks,
    explicit_fallback_chain,
    readable_model_name,
    record_fallback_event_chain,
    resolve_fallback_chain,
)
from domains.gateway.domain.router_model_name import encode_router_model_name

_TEAM = uuid.uuid4()


def _response_with_headers(headers: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(_hidden_params={"additional_headers": headers})


def test_readable_decodes_router_encoded_name() -> None:
    encoded = encode_router_model_name(_TEAM, "smart-route")
    assert readable_model_name(encoded) == "smart-route"
    assert readable_model_name("plain-model") == "plain-model"
    assert readable_model_name(None) is None


def test_attempted_fallbacks_parses_header() -> None:
    assert attempted_fallbacks(_response_with_headers({"x-litellm-attempted-fallbacks": 2})) == 2
    assert attempted_fallbacks(_response_with_headers({})) == 0
    assert attempted_fallbacks(SimpleNamespace()) == 0


def test_no_fallback_returns_empty() -> None:
    """未发生 failover（attempted=0）时链为空。"""
    response = _response_with_headers({"x-litellm-attempted-fallbacks": 0})
    chain = resolve_fallback_chain(
        metadata={"gateway_route_name": "smart-route"},
        kwargs={"model": encode_router_model_name(_TEAM, "smart-route")},
        response_obj=response,
    )
    assert chain == []


def test_header_derived_chain_on_fallback() -> None:
    """主模型失败 → 备用成功：由 header 推断出 [请求别名, 实际应答模型]。"""
    response = _response_with_headers(
        {
            "x-litellm-attempted-fallbacks": 1,
            "x-litellm-model-group": encode_router_model_name(_TEAM, "backup-route"),
        }
    )
    kwargs = {
        "model": encode_router_model_name(_TEAM, "backup-route"),
        "litellm_params": {"model_info": {"gateway_real_model": "claude-3-5-sonnet"}},
    }
    chain = resolve_fallback_chain(
        metadata={"gateway_route_name": "smart-route"},
        kwargs=kwargs,
        response_obj=response,
    )
    assert chain == ["smart-route", "claude-3-5-sonnet"]


def test_explicit_chain_takes_priority() -> None:
    """显式 gateway_fallback_chain 优先于 header 推断。"""
    response = _response_with_headers({"x-litellm-attempted-fallbacks": 1})
    chain = resolve_fallback_chain(
        metadata={"gateway_fallback_chain": ["a", "b", "c"]},
        kwargs={"model": "x"},
        response_obj=response,
    )
    assert chain == ["a", "b", "c"]


def test_explicit_chain_accepts_str() -> None:
    assert explicit_fallback_chain({"gateway_fallback_chain": "only"}) == ["only"]
    assert explicit_fallback_chain({}) == []


def test_record_event_chain_populates_metadata() -> None:
    """fallback 事件钩子回填：origin(原模型组) → final(实际模型) 写入显式链。"""
    metadata: dict[str, object] = {}
    kwargs = {
        "model": encode_router_model_name(_TEAM, "backup-route"),
        "metadata": metadata,
        "litellm_params": {"model_info": {"gateway_real_model": "gpt-4o"}},
    }
    original = encode_router_model_name(_TEAM, "smart-route")
    result = record_fallback_event_chain(metadata, kwargs, original)
    assert result == ["smart-route", "gpt-4o"]
    assert metadata["gateway_fallback_chain"] == ["smart-route", "gpt-4o"]


def test_record_event_chain_dedup_and_append() -> None:
    """多跳 fallback：在已有链上去重追加。"""
    metadata: dict[str, object] = {"gateway_fallback_chain": ["smart-route", "mid-route"]}
    kwargs = {
        "model": "final-route",
        "metadata": metadata,
        "litellm_params": {"model_info": {"gateway_real_model": "final-real"}},
    }
    result = record_fallback_event_chain(metadata, kwargs, "mid-route")
    assert result == ["smart-route", "mid-route", "final-real"]
