"""
LiteLLM 模型标识拼装（Gateway 出站规则，纯函数无 I/O）。

前缀与 provider 是否匹配的业务校验见 ``domains.gateway.application.litellm_real_model_prefix``。
"""

from __future__ import annotations

from domains.gateway.domain.upstream_endpoint import credential_api_base

_PROVIDER_PREFIXES: frozenset[str] = frozenset(
    {"openai", "anthropic", "dashscope", "deepseek", "volcengine", "moonshot"}
)

# 业务 provider 名 → LiteLLM 原生 custom_llm_provider 名。
# 未在此映射中的 provider 且不在 LiteLLM LlmProviders 中的，
# 统一映射为 ``custom_openai``（LiteLLM 内置的 OpenAI 兼容端点 provider）。
_PROVIDER_TO_LITELLM: dict[str, str] = {
    "zhipuai": "zai",
}

# OpenAI 官方 API 端点前缀。当 ``provider=openai`` 但 ``api_base``
# 不匹配这些前缀时，说明是第三方 OpenAI 兼容端点，必须使用
# ``custom_openai``——否则 ``anthropic_messages()`` 会走 Responses API
# （``/responses``），而第三方端点只支持 ``/chat/completions``。
_OPENAI_OFFICIAL_API_BASE_PREFIXES: tuple[str, ...] = ("https://api.openai.com/",)


def _is_openai_official_endpoint(api_base: str | None) -> bool:
    """判断 api_base 是否指向 OpenAI 官方端点。"""
    if not api_base:
        return True  # 无 api_base 时走 provider 默认，视为官方
    return any(
        api_base.rstrip("/").startswith(p.rstrip("/")) for p in _OPENAI_OFFICIAL_API_BASE_PREFIXES
    )


def is_openai_official_endpoint(api_base: str | None) -> bool:
    """判断 api_base 是否指向 OpenAI 官方端点。"""
    return _is_openai_official_endpoint(api_base)


def normalize_gateway_stored_real_model(
    provider: str,
    model_id: str,
    *,
    api_base: str | None = None,
) -> str:
    """落库 / 出站 ``real_model``：OpenAI-compat 自定义端点存裸上游 id。

    Router OpenAI-compat 出站将 ``real_model`` 原样作为 ``model`` 参数；第三方端点
    （``custom_openai``）不接受 ``openai/`` 前缀（如 Agnes ``agnes-1.5-flash``）。
    官方 OpenAI 与其它 provider 仍走 ``build_litellm_model_id`` 前缀规则。
    """
    stripped = model_id.strip()
    if not stripped:
        return stripped
    provider_key = provider.strip().lower()
    if provider_key == "openai" and not _is_openai_official_endpoint(api_base):
        if stripped.lower().startswith("openai/"):
            return stripped.split("/", 1)[1]
        return stripped
    return build_litellm_model_id(provider_key, stripped)


def resolve_outbound_litellm_model(
    provider: str,
    real_model: str,
    *,
    api_base: str | None = None,
) -> str:
    """代理 / 探活出站时使用的 LiteLLM ``model`` 参数（与落库规则一致）。"""
    return normalize_gateway_stored_real_model(provider, real_model, api_base=api_base)


def normalize_stored_real_model_for_credential(
    provider: str,
    model_id: str,
    credential: object | None,
) -> str:
    """按凭据 endpoint 规范化落库 ``real_model``。"""
    return normalize_gateway_stored_real_model(
        provider.strip().lower(),
        model_id,
        api_base=credential_api_base(credential),
    )


def build_litellm_model_id(provider: str, model_id: str) -> str:
    """根据 provider + model_id 构建 LiteLLM 模型标识（运行时前缀拼装）。"""
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


def resolve_litellm_custom_llm_provider(
    provider: str,
    *,
    api_base: str | None = None,
) -> str:
    """将业务 provider 名映射为 LiteLLM 认识的 ``custom_llm_provider``。

    OpenAI-compat 出站路径通过 ``custom_llm_provider`` + ``api_base`` + ``api_key``
    路由到上游；LiteLLM 必须认识此 provider 名才能正确选择 HTTP handler。

    当 ``provider=openai`` 但 ``api_base`` 不是 OpenAI 官方端点时，
    返回 ``custom_openai`` 以确保 ``anthropic_messages()`` 走 Chat Completions
    路径（而非 Responses API）。
    """
    key = provider.strip().lower()
    if key == "openai" and not _is_openai_official_endpoint(api_base):
        return "custom_openai"
    return _PROVIDER_TO_LITELLM.get(key, key)


__all__ = [
    "build_litellm_model_id",
    "is_openai_official_endpoint",
    "normalize_gateway_stored_real_model",
    "normalize_stored_real_model_for_credential",
    "resolve_litellm_custom_llm_provider",
    "resolve_outbound_litellm_model",
]
