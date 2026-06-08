"""``_normalize_route_model`` — 日志 route_name / real_model 规范化。"""

from __future__ import annotations

from types import SimpleNamespace

from domains.gateway.infrastructure.callbacks.custom_logger import _normalize_route_model


def test_uses_metadata_gateway_route_name() -> None:
    """metadata 中 gateway_route_name 存在时，route_name 取该值。"""
    metadata = {
        "gateway_capability": "chat",
        "gateway_route_name": "kimi-for-coding",
    }
    kwargs = {"model": "gw/t/team-id/kimi-for-coding"}
    result = _normalize_route_model(metadata, kwargs, None)
    assert result[1] == "kimi-for-coding"


def test_fallback_to_kwargs_model_when_no_route_name() -> None:
    """metadata 中无 gateway_route_name 时，fallback 到 kwargs['model']。"""
    metadata = {"gateway_capability": "chat"}
    kwargs = {"model": "gw/t/team-id/some-model"}
    result = _normalize_route_model(metadata, kwargs, None)
    assert result[1] == "gw/t/team-id/some-model"


def test_prefers_response_model_for_real_model() -> None:
    """上游响应 model 存在时，real_model 优先取响应值。"""
    metadata = {"gateway_capability": "chat"}
    kwargs = {"model": "gw/t/team-id/kimi-for-coding"}
    response = SimpleNamespace(model="moonshot/kimi-for-coding")
    result = _normalize_route_model(metadata, kwargs, response)
    assert result[2] == "moonshot/kimi-for-coding"


def test_prefers_model_info_gateway_real_model_over_kwargs() -> None:
    """Router 回调 model_info 中有 gateway_real_model 时，优先于 kwargs['model']。"""
    metadata = {"gateway_capability": "chat"}
    kwargs = {
        "model": "gw/t/team-id/kimi-for-coding",
        "litellm_params": {
            "model_info": {"gateway_real_model": "kimi-for-coding"},
        },
    }
    result = _normalize_route_model(metadata, kwargs, None)
    assert result[2] == "kimi-for-coding"


def test_uses_kwargs_model_when_no_response_and_no_model_info() -> None:
    """无响应 model 且无 model_info 时，real_model fallback 到 kwargs['model']。"""
    metadata = {"gateway_capability": "chat"}
    kwargs = {"model": "some-direct-model"}
    result = _normalize_route_model(metadata, kwargs, None)
    assert result[2] == "some-direct-model"
