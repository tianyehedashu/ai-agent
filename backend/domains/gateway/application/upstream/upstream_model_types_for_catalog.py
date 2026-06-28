"""凭据探测：合并正则与 LiteLLM hint 推断 upstream model_types。"""

from __future__ import annotations

from domains.gateway.application.ports import LitellmCapabilityHintPort
from domains.gateway.domain.litellm.litellm_model_id import normalize_gateway_stored_real_model
from domains.gateway.domain.types import PERSONAL_MODEL_TYPES
from domains.gateway.domain.upstream.upstream_type_inference import (
    filter_valid_personal_model_types,
    infer_upstream_model_types,
)

from domains.gateway.application.catalog.config_catalog_sync import model_types_for_gateway_registration
from .litellm_capability_hint import (
    merge_litellm_capability_hints,
)


def infer_upstream_model_types_for_catalog(
    provider: str,
    upstream_id: str,
    owned_by: str | None = None,
    *,
    api_base: str | None = None,
    hint_port: LitellmCapabilityHintPort | None = None,
) -> tuple[str, ...]:
    """正则推断 ∪ LiteLLM fill_missing hint 推导的 model_types（探测列表用）。"""
    regex_types = infer_upstream_model_types(provider, upstream_id, owned_by)
    real_model = normalize_gateway_stored_real_model(provider, upstream_id.strip(), api_base=api_base)
    hinted_tags = merge_litellm_capability_hints(
        {},
        provider=provider,
        real_model=real_model,
        hint_port=hint_port,
        mode="fill_missing",
        skip_hints=False,
    )
    litellm_types = model_types_for_gateway_registration(hinted_tags, "chat")
    merged: list[str] = []
    for candidate in (*regex_types, *litellm_types):
        if candidate in PERSONAL_MODEL_TYPES and candidate not in merged:
            merged.append(candidate)
    return filter_valid_personal_model_types(tuple(merged))


__all__ = ["infer_upstream_model_types_for_catalog"]
