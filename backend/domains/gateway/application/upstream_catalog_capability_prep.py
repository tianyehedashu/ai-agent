"""探测目录与写侧落库共用的能力推导（正则 + LiteLLM hint → capability + tags）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.upstream_model_types_for_catalog import (
    infer_upstream_model_types_for_catalog,
)
from domains.gateway.domain.litellm_capability_mapping import LITELLM_CAPABILITY_TAG_KEYS
from domains.gateway.domain.model_types_tags import (
    model_types_for_capability_write,
    resolve_catalog_write_capability,
    tags_from_model_types,
)
from domains.gateway.domain.upstream_type_inference import (
    infer_non_personal_gateway_capability,
)


def prepare_gateway_write_from_upstream_catalog(
    *,
    provider: str,
    upstream_id: str,
    owned_by: str | None = None,
    api_base: str | None = None,
    base_tags: dict[str, Any] | None = None,
    capability_override: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """与探测列表同源：推断 model_types → capability + supports_* 预填 tags。

    返回 ``(capability, tags)``，调用方再交给 ``build_gateway_model_tags``。
    """
    merged = dict(base_tags or {})
    prov = provider.strip().lower()
    raw_id = upstream_id.strip()
    if not raw_id:
        return capability_override or "chat", merged

    non_personal_cap = infer_non_personal_gateway_capability(raw_id)
    if non_personal_cap:
        return non_personal_cap, merged

    model_types = infer_upstream_model_types_for_catalog(
        prov,
        raw_id,
        owned_by,
        api_base=api_base,
    )
    if not model_types:
        if capability_override:
            return capability_override, merged
        return None, merged

    capability = resolve_catalog_write_capability(
        model_types,
        capability_override=capability_override,
    )
    write_types = model_types_for_capability_write(model_types, capability)
    merged = tags_from_model_types(
        list(write_types),
        existing_tags=merged,
        capability=capability,
        clear_unselected=False,
    )
    return capability, merged


def should_apply_catalog_prep_to_base_tags(tags: dict[str, Any] | None) -> bool:
    """创建时 tags 为空或无可推导能力键时，应用目录推断。"""
    if not tags:
        return True
    return not any(key in tags for key in LITELLM_CAPABILITY_TAG_KEYS)


__all__ = [
    "prepare_gateway_write_from_upstream_catalog",
    "should_apply_catalog_prep_to_base_tags",
]
