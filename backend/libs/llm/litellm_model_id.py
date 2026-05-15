"""
LiteLLM 模型标识拼装工具

把 ``provider`` + ``model_id`` 拼成 LiteLLM 可识别的模型标识，规则：

- 已含 ``/`` 的 model_id 视为 vendor 前缀齐全，原样返回；
- ``zhipuai`` → ``zai/<model_id>``；
- ``dashscope`` / ``deepseek`` / ``volcengine`` → ``<provider>/<model_id>``；
- 其它（``openai``、``anthropic``、``custom``、未知 provider）→ 原样返回。
"""

from __future__ import annotations

_PROVIDER_PREFIXES: frozenset[str] = frozenset({"dashscope", "deepseek", "volcengine"})


def build_litellm_model_id(provider: str, model_id: str) -> str:
    """根据 provider + model_id 构建 LiteLLM 模型标识。"""
    if not model_id:
        return model_id
    if "/" in model_id:
        return model_id
    if provider == "zhipuai":
        return f"zai/{model_id}"
    if provider in _PROVIDER_PREFIXES:
        return f"{provider}/{model_id}"
    return model_id


__all__ = ["build_litellm_model_id"]
