"""route_capability 路由级能力交集聚合单测。"""

from domains.gateway.domain.catalog.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.proxy.temperature_policy import (
    DEFAULT_CLIENT_TEMPERATURE,
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
)
from domains.gateway.domain.proxy.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_NONE,
)
from domains.gateway.domain.route.route_capability import route_capability_snapshot


def test_empty_returns_none() -> None:
    assert route_capability_snapshot([]) is None


def test_single_returns_same_snapshot() -> None:
    snap = ModelCapabilitySnapshot(supports_streaming=False, supports_vision=True)
    out = route_capability_snapshot([snap])
    assert out is snap


def test_boolean_intersection_all_true() -> None:
    a = ModelCapabilitySnapshot(supports_streaming=True, supports_vision=True)
    b = ModelCapabilitySnapshot(supports_streaming=True, supports_vision=True)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.supports_streaming is True
    assert out.supports_vision is True


def test_boolean_intersection_one_false() -> None:
    """任一 primary 不支持则路由不支持（保证调度到该 deployment 安全）。"""
    a = ModelCapabilitySnapshot(supports_streaming=True)
    b = ModelCapabilitySnapshot(supports_streaming=False)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.supports_streaming is False
    assert out.supports_tools is True  # 默认 True ∩ True


def test_thinking_param_consistent_kept() -> None:
    a = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_ANTHROPIC)
    b = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_ANTHROPIC)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.thinking_param == THINKING_PARAM_ANTHROPIC


def test_thinking_param_inconsistent_degrades_to_none() -> None:
    """思考模式不一致时退化为 NONE（最宽松：不强制开启思考）。"""
    a = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_ANTHROPIC)
    b = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DASHSCOPE)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.thinking_param == THINKING_PARAM_NONE


def test_temperature_policy_inconsistent_degrades_to_client() -> None:
    """温度策略不一致时退化为 CLIENT（交由客户端控制）。"""
    a = ModelCapabilitySnapshot(temperature_policy=TEMPERATURE_POLICY_FIXED_1)
    b = ModelCapabilitySnapshot(temperature_policy=TEMPERATURE_POLICY_CLIENT)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.temperature_policy == TEMPERATURE_POLICY_CLIENT
    assert out.temperature_default == DEFAULT_CLIENT_TEMPERATURE


def test_temperature_policy_consistent_keeps_default() -> None:
    """温度策略一致时保留首项的 default（与 policy 配套）。"""
    a = ModelCapabilitySnapshot(
        temperature_policy=TEMPERATURE_POLICY_FIXED_1, temperature_default=1.0
    )
    b = ModelCapabilitySnapshot(
        temperature_policy=TEMPERATURE_POLICY_FIXED_1, temperature_default=1.0
    )
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.temperature_policy == TEMPERATURE_POLICY_FIXED_1
    assert out.temperature_default == 1.0


def test_context_window_takes_min() -> None:
    """上下文窗口取最保守值（min）。"""
    a = ModelCapabilitySnapshot(context_window=8192)
    b = ModelCapabilitySnapshot(context_window=4096)
    c = ModelCapabilitySnapshot(context_window=16384)
    out = route_capability_snapshot([a, b, c])
    assert out is not None
    assert out.context_window == 4096


def test_max_reference_images_takes_min() -> None:
    a = ModelCapabilitySnapshot(max_reference_images=4)
    b = ModelCapabilitySnapshot(max_reference_images=1)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.max_reference_images == 1


def test_mixed_capability_realistic_route() -> None:
    """真实路由场景：deepseek-chat（支持流式/tools）+ 某镜像（不支持流式）。

    路由应保证最低能力：不支持流式，支持 tools。
    """
    a = ModelCapabilitySnapshot(supports_streaming=True, supports_tools=True)
    b = ModelCapabilitySnapshot(supports_streaming=False, supports_tools=True)
    out = route_capability_snapshot([a, b])
    assert out is not None
    assert out.supports_streaming is False
    assert out.supports_tools is True
