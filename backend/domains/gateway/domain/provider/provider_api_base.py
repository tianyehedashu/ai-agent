"""各 Provider 官方 API Base 默认值（纯函数 SSOT，无 I/O）。"""

from __future__ import annotations

from domains.gateway.domain.upstream.upstream_endpoint import resolve_upstream_endpoint
from domains.gateway.domain.upstream.upstream_profile import UpstreamProtocol, default_profile_id
from domains.gateway.domain.upstream.upstream_profile_registry import get_upstream_profile

_DEFAULT_API_BASE_BY_PROVIDER: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipuai": "https://open.bigmodel.cn/api/paas/v4",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "moonshot": "https://api.moonshot.ai/v1",
}


def get_default_api_base(provider: str) -> str | None:
    """返回 provider 的内置默认 api_base；anthropic/custom 等须显式配置时返回 None。"""
    key = (provider or "").strip().lower()
    if not key:
        return None
    profile = get_upstream_profile(None, provider=key)
    openai_base = profile.api_bases.get(UpstreamProtocol.OPENAI_COMPAT)
    if openai_base:
        return openai_base
    return _DEFAULT_API_BASE_BY_PROVIDER.get(key)


def resolve_effective_api_base(provider: str, api_base: str | None) -> str | None:
    """凭据或 env 上的 base 为空时回退到 profile 默认 OpenAI-compat 根。"""
    return resolve_upstream_endpoint(
        provider=provider,
        profile_id=None,
        api_base=api_base,
        protocol=UpstreamProtocol.OPENAI_COMPAT,
    )


def resolve_effective_api_base_with_profile(
    provider: str,
    api_base: str | None,
    profile_id: str | None,
) -> str | None:
    """带 profile 的 OpenAI-compat 有效 base（凭据写侧 / Router 复用）。"""
    return resolve_upstream_endpoint(
        provider=provider,
        profile_id=profile_id,
        api_base=api_base,
        protocol=UpstreamProtocol.OPENAI_COMPAT,
    )


__all__ = [
    "default_profile_id",
    "get_default_api_base",
    "resolve_effective_api_base",
    "resolve_effective_api_base_with_profile",
]
