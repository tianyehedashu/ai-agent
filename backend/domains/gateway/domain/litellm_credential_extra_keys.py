"""按 provider 列出从 ``ProviderCredential.extra`` 透传给 LiteLLM 的字段白名单。

与前端 ``frontend/src/features/gateway-credentials/provider-schemas.ts``
的 ``extraFields[].key`` 必须保持一致——白名单决定 router 拼装 deployment 时
哪些 extra 字段会真正生效；不在表中的 key 会被静默丢弃，避免误把任意字段
塞给 LiteLLM 触发不可预期的行为。

设计要点：
- 白名单按 provider 标准化 (lowercase, strip) 后查询；未声明的 provider
  fallback 到 ``_COMMON_KEYS`` —— 仅放真正通用的字段。
- Bedrock 把 ``api_key`` 解密结果重命名为 ``aws_access_key_id`` 在 router
  侧由 ``API_KEY_RENAME`` 表声明。
"""

from __future__ import annotations

from typing import Final

# 注意：这些 key 必须与 LiteLLM 对应 provider 期望的参数名严格一致。
_COMMON_KEYS: Final[tuple[str, ...]] = ()

_EXTRA_KEYS_BY_PROVIDER: Final[dict[str, tuple[str, ...]]] = {
    "openai": ("organization", "project_id"),
    "anthropic": (),
    "azure": ("api_version",),
    "bedrock": ("aws_secret_access_key", "aws_region_name", "aws_session_token"),
    "gemini": (),
    "vertex_ai": ("vertex_project", "vertex_location", "vertex_credentials"),
    "dashscope": ("workspace_id",),
    "deepseek": (),
    "volcengine": ("region", "endpoint_id"),
    "zhipuai": (),
    "cohere": (),
    "mistral": (),
    "fireworks": (),
    "together_ai": (),
}

# Provider 用非 ``api_key`` 名称鉴权时，把解密后的 api_key 值映射为该 key。
API_KEY_RENAME: Final[dict[str, str]] = {
    "bedrock": "aws_access_key_id",
}


def credential_extra_keys_for_litellm(provider: str) -> tuple[str, ...]:
    """返回该 provider 允许透传给 LiteLLM 的 extra 字段名。"""
    key = (provider or "").strip().lower()
    return _EXTRA_KEYS_BY_PROVIDER.get(key, _COMMON_KEYS)


def litellm_api_key_param_name(provider: str) -> str:
    """该 provider 在 LiteLLM 中接收 API Key 的参数名（多数为 ``api_key``）。"""
    key = (provider or "").strip().lower()
    return API_KEY_RENAME.get(key, "api_key")


__all__ = [
    "API_KEY_RENAME",
    "credential_extra_keys_for_litellm",
    "litellm_api_key_param_name",
]
