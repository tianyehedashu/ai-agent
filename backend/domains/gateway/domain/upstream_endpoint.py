"""解析凭据/模型出站 api_base（统一 Router、Probe、Direct）。"""

from __future__ import annotations

from domains.gateway.domain.upstream_profile import UpstreamProtocol
from domains.gateway.domain.upstream_profile_registry import (
    get_upstream_profile,
    list_profiles_for_provider,
)


def resolve_upstream_endpoint(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
    protocol: UpstreamProtocol,
) -> str | None:
    """按 provider + profile + 用户覆盖解析有效 api_base。

    - ``api_base`` 非空：视为用户覆盖，经 profile ``normalize_rules`` 规范化。
    - ``api_base`` 为空：使用 profile 在该 protocol 下的默认根。
    """
    profile = get_upstream_profile(profile_id, provider=provider)
    return profile.normalize_api_base(api_base, protocol=protocol)


def resolve_openai_compat_api_base_for_storage(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
) -> str | None:
    """凭据落库前：将 OpenAI-compat 根规范化后写入 ``api_base`` 列。"""
    return resolve_upstream_endpoint(
        provider=provider,
        profile_id=profile_id,
        api_base=api_base,
        protocol=UpstreamProtocol.OPENAI_COMPAT,
    )


def effective_api_bases_for_credential(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
) -> dict[str, str]:
    """管理 API 展示：各协议下的有效根（仅返回已解析的非空值）。"""
    profile = get_upstream_profile(profile_id, provider=provider)
    out: dict[str, str] = {}
    for proto in (UpstreamProtocol.OPENAI_COMPAT, UpstreamProtocol.ANTHROPIC_NATIVE):
        endpoint = resolve_upstream_endpoint(
            provider=provider,
            profile_id=profile_id,
            api_base=api_base,
            protocol=proto,
        )
        if endpoint:
            out[proto.value] = endpoint
    # 若 profile 仅有 openai 默认且用户未填 anthropic，不强行返回
    if UpstreamProtocol.ANTHROPIC_NATIVE.value not in out:
        native_default = profile.api_bases.get(UpstreamProtocol.ANTHROPIC_NATIVE)
        if native_default and not (api_base or "").strip():
            out[UpstreamProtocol.ANTHROPIC_NATIVE.value] = native_default
    return out


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
    "effective_api_bases_for_credential",
    "infer_profile_id_from_env_api_base",
    "resolve_openai_compat_api_base_for_storage",
    "resolve_upstream_endpoint",
]
