"""凭据 ``is_active`` 与注册模型 ``enabled`` 的级联标记（纯函数）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.types import CREDENTIAL_CASCADE_DISABLED_TAG


def apply_credential_cascade_disable_tags(tags: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(tags or {})
    merged[CREDENTIAL_CASCADE_DISABLED_TAG] = True
    return merged


def clear_credential_cascade_disable_tags(tags: dict[str, Any] | None) -> dict[str, Any] | None:
    if not tags or CREDENTIAL_CASCADE_DISABLED_TAG not in tags:
        return tags
    merged = dict(tags)
    merged.pop(CREDENTIAL_CASCADE_DISABLED_TAG, None)
    return merged or None


def was_credential_cascade_disabled(tags: dict[str, Any] | None) -> bool:
    return bool((tags or {}).get(CREDENTIAL_CASCADE_DISABLED_TAG))


__all__ = [
    "CREDENTIAL_CASCADE_DISABLED_TAG",
    "apply_credential_cascade_disable_tags",
    "clear_credential_cascade_disable_tags",
    "was_credential_cascade_disabled",
]
