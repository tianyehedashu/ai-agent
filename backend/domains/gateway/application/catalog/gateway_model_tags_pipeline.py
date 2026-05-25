"""GatewayModel.tags 写侧统一流水线（LiteLLM hint + enrich）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from domains.gateway.application.catalog.litellm_capability_hint import (
    merge_litellm_capability_hints,
)
from domains.gateway.application.ports import LitellmCapabilityHintPort
from domains.gateway.domain.litellm_capability_mapping import HintMergeMode
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_NONE,
    effective_supports_reasoning,
    enrich_gateway_model_tags,
)


def build_gateway_model_tags(
    base_tags: dict[str, Any] | None,
    *,
    provider: str,
    real_model: str,
    hint_port: LitellmCapabilityHintPort | None = None,
    on_hint_thinking_param: Callable[[str], None] | None = None,
    hint_mode: HintMergeMode = "fill_missing",
    skip_hints: bool = False,
) -> dict[str, Any]:
    """合并 LiteLLM 能力 hint 后 enrich tags（显式 thinking_param 永不覆盖）。"""
    tags = merge_litellm_capability_hints(
        dict(base_tags or {}),
        provider=provider,
        real_model=real_model,
        hint_port=hint_port,
        mode=hint_mode,
        skip_hints=skip_hints,
    )
    hint_tp = tags.pop("_litellm_hint_thinking_param", None)
    if hint_tp and on_hint_thinking_param is not None:
        on_hint_thinking_param(str(hint_tp))
    tags = enrich_gateway_model_tags(tags, provider=provider, real_model=real_model)
    thinking_param = str(tags.get("thinking_param") or THINKING_PARAM_NONE)
    tags["supports_reasoning"] = effective_supports_reasoning(tags, thinking_param)
    return tags


__all__ = ["build_gateway_model_tags"]
