"""DashScope Embedding 直连策略（纯函数，无 HTTP/IO）。

LiteLLM ``aembedding`` 对 ``dashscope`` provider 映射不完整，会抛出
``Unmapped LLM provider``。DashScope 提供 OpenAI 兼容的
``/v1/embeddings``，本模块构建请求快照；HTTP 在 ``infrastructure/upstream``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.provider_api_base import (
    get_default_api_base,
    resolve_effective_api_base,
)

DEFAULT_DASHSCOPE_COMPAT_API_BASE = (
    get_default_api_base("dashscope") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
)


@dataclass(frozen=True, slots=True)
class DashscopeEmbeddingRequest:
    """DashScope OpenAI 兼容 Embedding 请求快照。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


def should_use_dashscope_direct_embedding(provider: str) -> bool:
    """是否应绕过 LiteLLM Router / ``aembedding``，改走兼容端点直连。"""
    return (provider or "").strip().lower() == "dashscope"


def normalize_dashscope_embedding_model(model_id: str) -> str:
    """将 ``real_model`` / ``dashscope/...`` 规范为上游 ``model`` 字段。"""
    cleaned = (model_id or "").strip()
    if not cleaned:
        return cleaned
    lower = cleaned.lower()
    if lower.startswith("dashscope/"):
        return cleaned.split("/", 1)[1]
    return cleaned


def _coerce_embedding_input(raw: Any) -> str | list[str]:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        if not raw:
            return []
        if all(isinstance(item, str) for item in raw):
            return raw
        return [str(item) for item in raw]
    return str(raw)


def build_dashscope_embedding_request(
    *,
    api_key: str,
    api_base: str | None,
    model_id: str,
    input_payload: Any,
) -> DashscopeEmbeddingRequest:
    """根据凭据与输入构建 OpenAI 兼容 Embedding 请求。"""
    base = (resolve_effective_api_base("dashscope", api_base) or DEFAULT_DASHSCOPE_COMPAT_API_BASE).rstrip(
        "/"
    )
    upstream_model = normalize_dashscope_embedding_model(model_id)
    return DashscopeEmbeddingRequest(
        url=f"{base}/embeddings",
        auth_header=f"Bearer {api_key}",
        json_body={
            "model": upstream_model,
            "input": _coerce_embedding_input(input_payload),
        },
    )


__all__ = [
    "DEFAULT_DASHSCOPE_COMPAT_API_BASE",
    "DashscopeEmbeddingRequest",
    "build_dashscope_embedding_request",
    "normalize_dashscope_embedding_model",
    "should_use_dashscope_direct_embedding",
]
