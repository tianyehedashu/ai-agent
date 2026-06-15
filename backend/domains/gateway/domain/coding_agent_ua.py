"""Coding Plan 出站 User-Agent 注入（Router deployment / 直连 kwargs 共用）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.upstream_profile_registry import get_upstream_profile


def resolve_coding_agent_ua(
    *,
    credential_profile_id: str | None,
    provider: str,
) -> str | None:
    """解析 profile 声明的 Coding Agent ``User-Agent``；无则 ``None``。"""
    profile = get_upstream_profile(credential_profile_id, provider=provider)
    ua = profile.coding_agent_ua
    return ua.strip() if isinstance(ua, str) and ua.strip() else None


def apply_coding_agent_ua_litellm_params(
    params: dict[str, Any],
    *,
    credential_profile_id: str | None,
    provider: str,
) -> dict[str, Any]:
    """在 ``litellm_params`` / 直连 kwargs 上写入 ``extra_headers["User-Agent"]``。"""
    ua = resolve_coding_agent_ua(
        credential_profile_id=credential_profile_id,
        provider=provider,
    )
    if ua is None:
        return params
    headers = dict(params.get("extra_headers") or {})
    headers["User-Agent"] = ua
    params["extra_headers"] = headers
    return params


__all__ = [
    "apply_coding_agent_ua_litellm_params",
    "resolve_coding_agent_ua",
]
