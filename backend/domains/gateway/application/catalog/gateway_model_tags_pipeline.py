"""GatewayModel.tags 写侧统一流水线（LiteLLM hint + enrich）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from domains.gateway.application.catalog.litellm_capability_hint import (
    merge_litellm_capability_hints,
)
from domains.gateway.application.ports import LitellmCapabilityHintPort
from domains.gateway.domain.litellm_capability_mapping import HintMergeMode
from domains.gateway.domain.temperature_policy import UPSTREAM_PROFILE_ID_TAG
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_NONE,
    effective_supports_reasoning,
    enrich_gateway_model_tags,
)


def merge_tags_patch(
    base: dict[str, Any] | None,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """增量合并 tags；``None`` 值表示删除对应键。

    ``context_window`` 显式清空时写入 ``0``（与 ``model_capability._coerce_context_window``
    未知语义一致），避免 LiteLLM ``fill_missing`` 再次注入。
    """
    merged = dict(base or {})
    for key, value in patch.items():
        if value is None:
            if key == "context_window":
                merged[key] = 0
            else:
                merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def build_gateway_model_tags(
    base_tags: dict[str, Any] | None,
    *,
    provider: str,
    real_model: str,
    upstream_profile_id: str | None = None,
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
    if upstream_profile_id and upstream_profile_id.strip():
        tags[UPSTREAM_PROFILE_ID_TAG] = upstream_profile_id.strip()
    tags = enrich_gateway_model_tags(tags, provider=provider, real_model=real_model)
    thinking_param = str(tags.get("thinking_param") or THINKING_PARAM_NONE)
    tags["supports_reasoning"] = effective_supports_reasoning(tags, thinking_param)
    return tags


__all__ = ["build_gateway_model_tags", "merge_tags_patch"]
