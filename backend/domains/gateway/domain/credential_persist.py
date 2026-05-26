"""凭据写侧 api_base / profile_id 规范化（纯函数）。"""

from __future__ import annotations

from domains.gateway.domain.upstream_endpoint import resolve_openai_compat_api_base_for_storage


def normalize_credential_write_fields(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    existing_api_base: str | None = None,
    existing_profile_id: str | None = None,
    touch_api_base: bool = True,
) -> tuple[str | None, str | None]:
    """返回落库用的 ``(api_base, profile_id)``。

    ``touch_api_base=False`` 时仅更新 profile_id 不改动 api_base（极少用）。
    """
    pid = profile_id if profile_id is not None else existing_profile_id
    raw_base = api_base if api_base is not None else existing_api_base
    if not touch_api_base and api_base is None:
        return (existing_api_base, pid)
    normalized = resolve_openai_compat_api_base_for_storage(
        provider=provider,
        profile_id=pid,
        api_base=raw_base,
    )
    return (normalized, pid)


__all__ = ["normalize_credential_write_fields"]
