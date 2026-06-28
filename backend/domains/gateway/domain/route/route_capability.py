"""路由级能力聚合：多 primary 模型能力取交集，保证 Router 调度到任一 deployment 均安全。

背景：``GatewayRoute`` 把多个 ``primary_models`` 注册为同一 ``virtual_model``，由 LiteLLM
Router 按 ``strategy`` 调度。``UpstreamAdapter`` 在 Router 选 deployment **之前** 改写出站
kwargs，因此不能用"第一条 primary"的能力——若 primary 间能力不一致，调度到弱能力 deployment
时会向上游发送不合规请求（如对不支持流式的模型发 ``stream=true``）。

语义：交集（intersection）—— 路由能保证的"最低能力"。

- 布尔能力（``supports_*``）：``all`` 为 True 才为 True
- 枚举能力（``thinking_param`` / ``temperature_policy``）：所有 primary 一致才取该值，否则退
  化为最宽松默认（``THINKING_PARAM_NONE`` / ``TEMPERATURE_POLICY_CLIENT``）
- 数值能力（``context_window`` / ``max_reference_images``）：取 ``min``（最保守）

注：``temperature_default`` 与 ``temperature_policy`` 配套；当 policy 退化为 CLIENT 时，
default 取所有 primary 的 ``max``（允许客户端更激进地提温度）。
"""

from __future__ import annotations

from domains.gateway.domain.catalog.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.proxy.temperature_policy import (
    DEFAULT_CLIENT_TEMPERATURE,
    TEMPERATURE_POLICY_CLIENT,
)
from domains.gateway.domain.proxy.thinking_param import THINKING_PARAM_NONE


def route_capability_snapshot(
    snapshots: list[ModelCapabilitySnapshot],
) -> ModelCapabilitySnapshot | None:
    """聚合多 primary 能力快照为路由级快照。

    Args:
        snapshots: 非空 primary 能力快照列表。

    Returns:
        路由级聚合快照；空列表返回 ``None``（调用方应回退到单模型路径）。
    """
    if not snapshots:
        return None
    if len(snapshots) == 1:
        return snapshots[0]

    return ModelCapabilitySnapshot(
        supports_tools=all(s.supports_tools for s in snapshots),
        supports_reasoning=all(s.supports_reasoning for s in snapshots),
        thinking_param=_intersection_enum(
            [s.thinking_param for s in snapshots], THINKING_PARAM_NONE
        ),
        temperature_policy=_intersection_enum(
            [s.temperature_policy for s in snapshots], TEMPERATURE_POLICY_CLIENT
        ),
        temperature_default=_temperature_default_aggregate(snapshots),
        supports_json_mode=all(s.supports_json_mode for s in snapshots),
        supports_vision=all(s.supports_vision for s in snapshots),
        supports_streaming=all(s.supports_streaming for s in snapshots),
        supports_image_gen=all(s.supports_image_gen for s in snapshots),
        supports_txt2img=all(s.supports_txt2img for s in snapshots),
        supports_img2img=all(s.supports_img2img for s in snapshots),
        supports_video_gen=all(s.supports_video_gen for s in snapshots),
        supports_image_to_video=all(s.supports_image_to_video for s in snapshots),
        max_reference_images=min(s.max_reference_images for s in snapshots),
        context_window=min(s.context_window for s in snapshots),
    )


def _intersection_enum(values: list[str], fallback: str) -> str:
    """所有值一致则取该值，否则退化为 fallback。"""
    first = values[0]
    return first if all(v == first for v in values) else fallback


def _temperature_default_aggregate(snapshots: list[ModelCapabilitySnapshot]) -> float:
    """policy 退化为 CLIENT 时，default 取 max（允许客户端更激进提温度）。

    policy 一致时取首项的 default（与 policy 配套）。
    """
    first = snapshots[0]
    if all(s.temperature_policy == first.temperature_policy for s in snapshots):
        return first.temperature_default
    return DEFAULT_CLIENT_TEMPERATURE


__all__ = ["route_capability_snapshot"]
