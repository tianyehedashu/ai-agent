"""火山方舟直连 LiteLLM 不可用时的 provider 判定（image / video 共用）。"""

from __future__ import annotations


def should_use_volcengine_direct_upstream(provider: str) -> bool:
    """是否应绕过 LiteLLM Router，改走火山方舟 HTTP API。"""
    return (provider or "").strip().lower() == "volcengine"


__all__ = ["should_use_volcengine_direct_upstream"]
