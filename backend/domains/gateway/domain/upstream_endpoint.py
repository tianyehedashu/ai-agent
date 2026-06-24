"""解析凭据/模型出站 api_base（统一 Router、Probe、Direct）。"""

from __future__ import annotations

from collections.abc import Mapping

from domains.gateway.domain.upstream_profile import UpstreamProtocol
from domains.gateway.domain.upstream_profile_registry import (
    get_upstream_profile,
    list_profiles_for_provider,
)

_CREDENTIAL_API_BASE_KEYS = frozenset(
    {UpstreamProtocol.OPENAI_COMPAT.value, UpstreamProtocol.ANTHROPIC_NATIVE.value}
)


def merge_credential_stored_api_bases(
    *,
    api_base: str | None,
    api_bases: Mapping[str, str] | None,
) -> dict[str, str]:
    """合并 legacy ``api_base`` 列与 ``api_bases`` JSONB 为用户覆盖集（未规范化）。"""
    out: dict[str, str] = {}
    if api_bases:
        for key, value in api_bases.items():
            if key not in _CREDENTIAL_API_BASE_KEYS:
                continue
            raw = (value or "").strip()
            if raw:
                out[key] = raw.rstrip("/")
    legacy = (api_base or "").strip()
    if legacy:
        out.setdefault(UpstreamProtocol.OPENAI_COMPAT.value, legacy.rstrip("/"))
    return out


def resolve_upstream_endpoint(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    protocol: UpstreamProtocol,
    api_bases: Mapping[str, str] | None = None,
) -> str | None:
    """按 provider + profile + 用户覆盖解析有效 api_base。

    - 凭据 ``api_bases[protocol]`` 或 legacy ``api_base``（OpenAI-compat）非空：
      视为用户覆盖，经 profile 规则规范化。
    - 均为空：使用 profile 在该 protocol 下的默认根。
    """
    profile = get_upstream_profile(profile_id, provider=provider)
    stored = merge_credential_stored_api_bases(api_base=api_base, api_bases=api_bases)
    override = stored.get(protocol.value)
    return profile.normalize_api_base(override, protocol=protocol)


def normalize_protocol_api_base_for_storage(
    *,
    provider: str,
    profile_id: str | None,
    protocol: UpstreamProtocol,
    api_base: str | None,
) -> str | None:
    """单协议 endpoint 落库前规范化；空字符串表示清除该 protocol 覆盖。"""
    raw = (api_base or "").strip()
    if not raw:
        return None
    profile = get_upstream_profile(profile_id, provider=provider)
    normalized = profile.normalize_api_base(raw, protocol=protocol)
    return normalized.rstrip("/") if normalized else None


def normalize_credential_api_bases_for_storage(
    *,
    provider: str,
    profile_id: str | None,
    api_bases: Mapping[str, str | None] | None,
    legacy_api_base: str | None = None,
) -> dict[str, str] | None:
    """凭据落库前：规范化各 protocol 覆盖；返回 None 表示无用户覆盖。"""
    merged_input: dict[str, str | None] = {}
    if api_bases:
        for key in _CREDENTIAL_API_BASE_KEYS:
            if key in api_bases:
                merged_input[key] = api_bases[key]
    if legacy_api_base is not None and UpstreamProtocol.OPENAI_COMPAT.value not in merged_input:
        merged_input[UpstreamProtocol.OPENAI_COMPAT.value] = legacy_api_base

    out: dict[str, str] = {}
    for key in _CREDENTIAL_API_BASE_KEYS:
        if key not in merged_input:
            continue
        protocol = UpstreamProtocol(key)
        normalized = normalize_protocol_api_base_for_storage(
            provider=provider,
            profile_id=profile_id,
            protocol=protocol,
            api_base=merged_input[key],
        )
        if normalized:
            out[key] = normalized
    return out or None


def resolve_openai_compat_api_base_for_storage(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    api_bases: Mapping[str, str | None] | None = None,
) -> str | None:
    """凭据落库前：OpenAI-compat 根（legacy ``api_base`` 列镜像）。"""
    stored = normalize_credential_api_bases_for_storage(
        provider=provider,
        profile_id=profile_id,
        api_bases=api_bases,
        legacy_api_base=api_base,
    )
    if stored and UpstreamProtocol.OPENAI_COMPAT.value in stored:
        return stored[UpstreamProtocol.OPENAI_COMPAT.value]
    if (api_base or "").strip():
        return normalize_protocol_api_base_for_storage(
            provider=provider,
            profile_id=profile_id,
            protocol=UpstreamProtocol.OPENAI_COMPAT,
            api_base=api_base,
        )
    return None


def effective_api_bases_for_credential(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    api_bases: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """管理 API 展示：各协议下的有效根（仅返回已解析的非空值）。"""
    out: dict[str, str] = {}
    for proto in (UpstreamProtocol.OPENAI_COMPAT, UpstreamProtocol.ANTHROPIC_NATIVE):
        endpoint = resolve_upstream_endpoint(
            provider=provider,
            profile_id=profile_id,
            api_base=api_base,
            api_bases=api_bases,
            protocol=proto,
        )
        if endpoint:
            out[proto.value] = endpoint
    return out


def credential_api_base(credential: object | None) -> str | None:
    """从凭据 ORM / 读模型取 OpenAI-compat 首选 api_base（落库规范化用）。"""
    if credential is None:
        return None
    legacy = getattr(credential, "api_base", None)
    bases = getattr(credential, "api_bases", None)
    merged = merge_credential_stored_api_bases(
        api_base=legacy if isinstance(legacy, str) else None,
        api_bases=bases if isinstance(bases, Mapping) else None,
    )
    return merged.get(UpstreamProtocol.OPENAI_COMPAT.value)


def infer_profile_id_from_env_api_base(
    provider: str,
    *,
    api_base: str | None,
) -> str | None:
    """从环境/配置中的 api_base 推断 profile（bootstrap sync 用）。"""
    base = (api_base or "").strip().rstrip("/")
    if not base:
        return None
    p = provider.lower().strip()
    for prof in list_profiles_for_provider(p):
        for endpoint in prof.api_bases.values():
            if endpoint and base == endpoint.rstrip("/"):
                return prof.id
    return None


__all__ = [
    "credential_api_base",
    "effective_api_bases_for_credential",
    "infer_profile_id_from_env_api_base",
    "merge_credential_stored_api_bases",
    "normalize_credential_api_bases_for_storage",
    "normalize_protocol_api_base_for_storage",
    "resolve_openai_compat_api_base_for_storage",
    "resolve_upstream_endpoint",
]
