"""凭据写侧 api_base / api_bases / profile_id 规范化（纯函数）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.upstream.upstream_endpoint import (
    normalize_credential_api_bases_for_storage,
    resolve_openai_compat_api_base_for_storage,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def normalize_credential_write_fields(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    api_bases: Mapping[str, str | None] | None = None,
    existing_api_base: str | None = None,
    existing_api_bases: Mapping[str, str] | None = None,
    existing_profile_id: str | None = None,
    touch_api_base: bool = True,
) -> tuple[str | None, dict[str, str] | None, str | None]:
    """返回落库用的 ``(api_base, api_bases, profile_id)``。

    ``touch_api_base=False`` 时仅更新 profile_id 不改动 endpoint 字段。
    PATCH 时 ``api_bases`` 与 ``api_base`` 合并已有 stored 值后再规范化。
    """
    pid = profile_id if profile_id is not None else existing_profile_id
    if not touch_api_base and api_base is None and api_bases is None:
        existing_dict = dict(existing_api_bases) if existing_api_bases else None
        return (existing_api_base, existing_dict, pid)

    merged_bases: dict[str, str | None] = {}
    if existing_api_bases:
        merged_bases.update(existing_api_bases)
    if api_bases:
        for key, value in api_bases.items():
            merged_bases[key] = value
    legacy_openai = api_base if api_base is not None else existing_api_base
    if api_base is not None:
        merged_bases["openai_compat"] = api_base

    stored_bases = normalize_credential_api_bases_for_storage(
        provider=provider,
        profile_id=pid,
        api_bases=merged_bases if merged_bases else None,
        legacy_api_base=legacy_openai if "openai_compat" not in merged_bases else None,
    )
    stored_legacy = resolve_openai_compat_api_base_for_storage(
        provider=provider,
        profile_id=pid,
        api_base=legacy_openai,
        api_bases=stored_bases,
    )
    return (stored_legacy, stored_bases, pid)


__all__ = ["normalize_credential_write_fields"]
