"""目录写侧：合并 LiteLLM 能力 hint 到 tags（不覆盖显式 thinking_param）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.ports import LitellmCapabilityHintPort
from domains.gateway.domain.litellm.litellm_capability_mapping import (
    HintMergeMode,
    apply_litellm_hints_to_tags,
    hints_without_reasoning,
)
from domains.gateway.domain.proxy.thinking_param import (
    THINKING_PARAM_VALUES,
    infer_thinking_param,
)
from domains.gateway.infrastructure.litellm.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
)

_DEFAULT_HINT: LitellmCapabilityHintPort = LitellmCapabilityHintAdapter()


def _has_explicit_thinking_param(tags: dict[str, Any]) -> bool:
    explicit = tags.get("thinking_param")
    return isinstance(explicit, str) and explicit.strip() in THINKING_PARAM_VALUES


def merge_litellm_capability_hints(
    tags: dict[str, Any],
    *,
    provider: str,
    real_model: str,
    hint_port: LitellmCapabilityHintPort | None = None,
    mode: HintMergeMode = "fill_missing",
    skip_hints: bool = False,
) -> dict[str, Any]:
    """合并 LiteLLM model_cost 能力标记到 tags。

    ``skip_hints=True`` 时跳过（配置托管种子模型）。
    显式 ``thinking_param`` 不被 LiteLLM reasoning hint 覆盖。
    """
    merged = dict(tags)
    if skip_hints:
        return merged

    port = hint_port or _DEFAULT_HINT
    hints = port.get_model_hints(provider=provider, real_model=real_model)
    if hints is None:
        return merged

    hints_for_apply = (
        hints_without_reasoning(hints) if _has_explicit_thinking_param(merged) else hints
    )
    merged = apply_litellm_hints_to_tags(merged, hints_for_apply, mode=mode)

    if _has_explicit_thinking_param(tags):
        return merged

    if merged.get("supports_reasoning") is True:
        inferred = infer_thinking_param(
            provider=provider,
            real_model=real_model,
            supports_reasoning=True,
            explicit=None,
        )
        if inferred != merged.get("thinking_param"):
            merged.setdefault("_litellm_hint_thinking_param", inferred)

    return merged


def merge_litellm_reasoning_hint(
    tags: dict[str, Any],
    *,
    provider: str,
    real_model: str,
    hint_port: LitellmCapabilityHintPort | None = None,
) -> dict[str, Any]:
    """向后兼容：仅 reasoning 路径（等价于 fill_missing 全量 merge）。"""
    return merge_litellm_capability_hints(
        tags,
        provider=provider,
        real_model=real_model,
        hint_port=hint_port,
        mode="fill_missing",
        skip_hints=False,
    )


__all__ = ["merge_litellm_capability_hints", "merge_litellm_reasoning_hint"]
