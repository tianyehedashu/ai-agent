"""Gateway 模型能力值对象（与 ``GatewayModel.tags`` / 出站适配对齐）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.proxy.temperature_policy import (
    DEFAULT_CLIENT_TEMPERATURE,
    TEMPERATURE_POLICY_CLIENT,
    resolve_temperature_default_from_tags,
    resolve_temperature_policy_from_tags,
)
from domains.gateway.domain.proxy.thinking_param import (
    THINKING_PARAM_NONE,
    resolve_thinking_param_from_tags,
)


@dataclass(frozen=True)
class ModelCapabilitySnapshot:
    """与 LLM 参数适配相关的模型能力（与 CatalogSeedModel / Gateway tags 字段对齐子集）。"""

    supports_tools: bool = True
    supports_reasoning: bool = False
    thinking_param: str = THINKING_PARAM_NONE
    temperature_policy: str = TEMPERATURE_POLICY_CLIENT
    temperature_default: float = DEFAULT_CLIENT_TEMPERATURE
    supports_json_mode: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_image_gen: bool = False
    supports_txt2img: bool = True
    supports_img2img: bool = False
    supports_video_gen: bool = False
    supports_image_to_video: bool = False
    max_reference_images: int = 0
    context_window: int = 0

    @property
    def features(self) -> frozenset[str]:
        result: set[str] = set()
        if self.supports_vision:
            result.add("vision")
        if self.supports_tools:
            result.add("tools")
        if self.supports_reasoning:
            result.add("reasoning")
        if self.supports_json_mode:
            result.add("json_mode")
        if self.supports_streaming:
            result.add("streaming")
        if self.supports_image_gen:
            result.add("image_gen")
        if self.supports_txt2img:
            result.add("txt2img")
        if self.supports_img2img:
            result.add("img2img")
        if self.supports_video_gen:
            result.add("video_gen")
        if self.supports_image_to_video:
            result.add("image_to_video")
        return frozenset(result)


def tags_to_capability_snapshot(
    tags: dict[str, Any],
    *,
    provider: str = "",
    real_model: str = "",
    credential_profile_id: str | None = None,
) -> ModelCapabilitySnapshot:
    """从 ``GatewayModel.tags`` 构建能力快照。"""
    supports_image_gen = bool(tags.get("supports_image_gen", False))
    default_txt2 = supports_image_gen
    default_img2 = supports_image_gen
    thinking_param = resolve_thinking_param_from_tags(
        tags, provider=provider, real_model=real_model
    )
    supports_reasoning = bool(tags.get("supports_reasoning", False)) or bool(
        tags.get("supports_reasoning_content", False)
    )
    if thinking_param != THINKING_PARAM_NONE:
        supports_reasoning = True
    temperature_policy = resolve_temperature_policy_from_tags(
        tags,
        thinking_param=thinking_param,
        real_model=real_model,
        credential_profile_id=credential_profile_id,
        provider=provider,
    )
    temperature_default = resolve_temperature_default_from_tags(tags)
    return ModelCapabilitySnapshot(
        supports_tools=bool(tags.get("supports_tools", True)),
        supports_reasoning=supports_reasoning,
        thinking_param=thinking_param,
        temperature_policy=temperature_policy,
        temperature_default=temperature_default,
        supports_json_mode=bool(tags.get("supports_json_mode", True)),
        supports_vision=bool(tags.get("supports_vision", False)),
        supports_streaming=bool(tags.get("supports_streaming", True)),
        supports_image_gen=supports_image_gen,
        supports_txt2img=bool(tags.get("supports_txt2img", default_txt2)),
        supports_img2img=bool(tags.get("supports_img2img", default_img2)),
        supports_video_gen=bool(tags.get("supports_video_gen", False)),
        supports_image_to_video=bool(tags.get("supports_image_to_video", False)),
        max_reference_images=int(tags.get("max_reference_images", 0) or 0),
        context_window=_coerce_context_window(tags.get("context_window")),
    )


def _coerce_context_window(value: Any) -> int:
    """上下文窗口（tokens）；非正整数视为未知（0）。"""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value.is_integer() and value > 0:
        return int(value)
    return 0


__all__ = ["ModelCapabilitySnapshot", "tags_to_capability_snapshot"]
