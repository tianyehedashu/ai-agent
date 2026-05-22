"""各 Provider 官方 API Base 默认值（纯函数 SSOT，无 I/O）。"""

from __future__ import annotations

_DEFAULT_API_BASE_BY_PROVIDER: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipuai": "https://open.bigmodel.cn/api/paas/v4",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
}


def get_default_api_base(provider: str) -> str | None:
    """返回 provider 的内置默认 api_base；anthropic/custom 等须显式配置时返回 None。"""
    key = (provider or "").strip().lower()
    if not key:
        return None
    return _DEFAULT_API_BASE_BY_PROVIDER.get(key)


def resolve_effective_api_base(provider: str, api_base: str | None) -> str | None:
    """凭据或 env 上的 base 为空时回退到 ``get_default_api_base``。"""
    stripped = (api_base or "").strip()
    if stripped:
        return stripped
    return get_default_api_base(provider)


__all__ = [
    "get_default_api_base",
    "resolve_effective_api_base",
]
