"""
LiteLLM 模型标识拼装工具

把 ``provider`` + ``model_id`` 拼成 LiteLLM 可识别的模型标识，规则：

- 已含 ``/`` 的 model_id 视为 vendor 前缀齐全（如 ``deepseek/deepseek-chat``、
  ``openai/gpt-4o``），原样返回；
- ``zhipuai`` → ``zai/<model_id>``（LiteLLM 用 ``zai/`` 前缀）；
- ``dashscope`` / ``deepseek`` / ``volcengine`` → ``<provider>/<model_id>``；
- 其它（``openai``、``anthropic``、``custom``、未知 provider）→ 原样返回。

``UserModelUseCase``（用户自定义模型）与 ``GatewayManagementWriteService``
（Gateway 团队模型）连通性测试都依赖同一份拼装逻辑，集中在此处避免漂移。
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
