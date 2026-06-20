"""Coding Plan 出站 User-Agent 注入（Router deployment / 直连 kwargs 共用）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.upstream_profile import UpstreamProtocol
from domains.gateway.domain.upstream_profile_registry import (
    get_upstream_profile,
    list_profiles_for_provider,
)


def _credential_openai_compat_api_base(credential: Any | None) -> str | None:
    """从凭据对象提取 OpenAI-compat api_base（优先 api_bases，兼容 legacy api_base）。"""
    if credential is None:
        return None
    api_bases = getattr(credential, "api_bases", None)
    if isinstance(api_bases, dict):
        for key in (UpstreamProtocol.OPENAI_COMPAT.value, "openai_compat"):
            raw = api_bases.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip().rstrip("/")
    legacy = getattr(credential, "api_base", None)
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip().rstrip("/")
    return None


def _infer_profile_id_from_credential_api_base(
    provider: str,
    credential: Any | None,
) -> str | None:
    """当凭据 endpoint 命中某 Coding profile 的默认 api_base 时，回退到该 profile。"""
    base = _credential_openai_compat_api_base(credential)
    if not base:
        return None
    p = provider.lower().strip()
    for prof in list_profiles_for_provider(p):
        if not prof.coding_agent_ua:
            continue
        for endpoint in prof.api_bases.values():
            if endpoint and base == endpoint.rstrip("/"):
                return prof.id
    return None


def _fallback_coding_agent_ua(provider: str, real_model: str | None) -> str | None:
    """按 provider + 上游真实模型名兜底：命中已知 Coding 模型时返回 profile 声明的 UA。"""
    p = provider.lower().strip()
    rm = (real_model or "").strip().lower()
    if p == "moonshot" and rm.startswith("kimi-for-coding"):
        profile = get_upstream_profile("moonshot.coding_plan", provider=provider)
        ua = profile.coding_agent_ua
        if isinstance(ua, str) and ua.strip():
            return ua.strip()
    return None


def resolve_coding_agent_ua(
    *,
    credential_profile_id: str | None,
    provider: str,
    credential: Any | None = None,
    real_model: str | None = None,
) -> str | None:
    """解析 profile 声明的 Coding Agent ``User-Agent``；无则按 api_base / 模型名兜底。"""
    profile = get_upstream_profile(credential_profile_id, provider=provider)
    ua = profile.coding_agent_ua
    if isinstance(ua, str) and ua.strip():
        return ua.strip()

    inferred_profile_id = _infer_profile_id_from_credential_api_base(provider, credential)
    if inferred_profile_id:
        profile = get_upstream_profile(inferred_profile_id, provider=provider)
        ua = profile.coding_agent_ua
        if isinstance(ua, str) and ua.strip():
            return ua.strip()

    ua = _fallback_coding_agent_ua(provider, real_model)
    if isinstance(ua, str) and ua.strip():
        return ua.strip()

    return None


def apply_coding_agent_ua_litellm_params(
    params: dict[str, Any],
    *,
    credential_profile_id: str | None,
    provider: str,
    credential: Any | None = None,
    real_model: str | None = None,
) -> dict[str, Any]:
    """在 ``litellm_params`` / 直连 kwargs 上写入 ``extra_headers["User-Agent"]``。"""
    ua = resolve_coding_agent_ua(
        credential_profile_id=credential_profile_id,
        provider=provider,
        credential=credential,
        real_model=real_model,
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
