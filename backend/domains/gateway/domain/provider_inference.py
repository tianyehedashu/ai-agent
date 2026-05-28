"""从模型标识推断上游 provider 键（Gateway 出站策略，纯函数）。"""

from __future__ import annotations


def infer_provider_name(model: str) -> str:
    """根据模型名称推断 LiteLLM provider 键。"""
    model_lower = model.lower()
    if "/" in model_lower:
        prefix = model_lower.split("/", 1)[0]
        if prefix == "zai":
            return "zhipuai"
        if prefix in {"dashscope", "deepseek", "volcengine", "moonshot", "openai", "anthropic"}:
            return prefix
    if model_lower.startswith("o1") or model_lower.startswith("o3"):
        return "openai"
    patterns = (
        ("claude", "anthropic"),
        ("gpt", "openai"),
        ("qwen", "dashscope"),
        ("deepseek", "deepseek"),
        ("doubao", "volcengine"),
        ("glm", "zhipuai"),
        ("kimi", "moonshot"),
        ("moonshot", "moonshot"),
    )
    for pattern, provider in patterns:
        if pattern in model_lower:
            return provider
    return "openai"


__all__ = ["infer_provider_name"]
