"""
LiteLLM 模型标识拼装（Gateway 出站规则，纯函数无 I/O）。

前缀与 provider 是否匹配的业务校验见 ``domains.gateway.application.litellm_real_model_prefix``。
"""

from __future__ import annotations

_PROVIDER_PREFIXES: frozenset[str] = frozenset(
    {"anthropic", "dashscope", "deepseek", "volcengine"}
)


def build_litellm_model_id(provider: str, model_id: str) -> str:
    """根据 provider + model_id 构建 LiteLLM 模型标识。"""
    if not model_id:
        return model_id
    provider_key = provider.strip().lower()
    if "/" in model_id:
        return model_id
    if provider_key == "zhipuai":
        return f"zai/{model_id}"
    if provider_key in _PROVIDER_PREFIXES:
        return f"{provider_key}/{model_id}"
    return model_id


__all__ = ["build_litellm_model_id"]
