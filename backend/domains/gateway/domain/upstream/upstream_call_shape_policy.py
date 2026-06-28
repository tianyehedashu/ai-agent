"""模型出站调用形策略（纯函数）。"""

from __future__ import annotations

from .upstream_profile import UpstreamCallShape
from .upstream_profile_registry import get_upstream_profile


def resolve_effective_upstream_call_shape(
    *,
    model_upstream_call_shape: str | None,
    credential_profile_id: str | None,
    provider: str,
) -> UpstreamCallShape:
    """模型显式配置优先；否则跟随凭据 profile 默认。"""
    if model_upstream_call_shape:
        raw = model_upstream_call_shape.strip().lower()
        if raw == UpstreamCallShape.ANTHROPIC_NATIVE.value:
            return UpstreamCallShape.ANTHROPIC_NATIVE
        return UpstreamCallShape.OPENAI_COMPAT
    profile = get_upstream_profile(credential_profile_id, provider=provider)
    return profile.default_call_shape


def anthropic_native_passthrough_enabled(
    *,
    call_shape: UpstreamCallShape,
    feature_flag: bool,
) -> bool:
    """是否尝试 Anthropic-native 出站（需 feature flag + 调用形）。"""
    return feature_flag and call_shape == UpstreamCallShape.ANTHROPIC_NATIVE


__all__ = [
    "anthropic_native_passthrough_enabled",
    "resolve_effective_upstream_call_shape",
]
