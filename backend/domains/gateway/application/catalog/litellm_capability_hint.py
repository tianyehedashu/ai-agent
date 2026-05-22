"""目录写侧：合并 LiteLLM reasoning 提示到 tags（不覆盖显式 thinking_param）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.thinking_param import THINKING_PARAM_VALUES, infer_thinking_param
from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
    LitellmCapabilityHintPort,
)

_DEFAULT_HINT: LitellmCapabilityHintPort = LitellmCapabilityHintAdapter()


def merge_litellm_reasoning_hint(
    tags: dict[str, Any],
    *,
    provider: str,
    real_model: str,
    hint_port: LitellmCapabilityHintPort | None = None,
) -> dict[str, Any]:
    """若 tags 无显式 ``thinking_param``，可用 LiteLLM hint 抬高 ``supports_reasoning`` 再推断。

    显式 ``thinking_param`` 与种子配置永不覆盖。
    """
    merged = dict(tags)
    explicit = merged.get("thinking_param")
    if isinstance(explicit, str) and explicit.strip() in THINKING_PARAM_VALUES:
        return merged

    port = hint_port or _DEFAULT_HINT
    hint = port.supports_reasoning(provider=provider, real_model=real_model)
    if hint is not True:
        return merged

    merged["supports_reasoning"] = True
    inferred = infer_thinking_param(
        provider=provider,
        real_model=real_model,
        supports_reasoning=True,
        explicit=None,
    )
    if inferred != merged.get("thinking_param"):
        merged.setdefault("_litellm_hint_thinking_param", inferred)
    return merged


__all__ = ["merge_litellm_reasoning_hint"]
