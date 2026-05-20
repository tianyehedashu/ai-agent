"""网关注册模型：上游 ``real_model`` 与 ``provider`` 的 LiteLLM 前缀一致性校验。

用户可见错误文案属于 Gateway 应用层；LiteLLM 模型 ID 拼装见 ``domains.gateway.domain.litellm_model_id``。
"""

from __future__ import annotations

_STRICT_PREFIX_PROVIDERS: frozenset[str] = frozenset(
    {"dashscope", "deepseek", "volcengine", "zhipuai"}
)


def litellm_prefix_violation_message(provider: str, model_id: str) -> str | None:
    """当 ``model_id`` 已含 ``/`` 时，校验首段是否与当前 ``provider`` 的 LiteLLM 前缀一致。

    - ``zhipuai`` 对应 LiteLLM 前缀 ``zai``；
    - ``dashscope`` / ``deepseek`` / ``volcengine`` 首段须与 provider 同名；
    - 其它 provider 不校验（避免误伤 ``azure/…``、``vertex_ai/…`` 等）。
    """
    stripped = model_id.strip()
    if "/" not in stripped:
        return None
    first = stripped.split("/", 1)[0]
    if provider not in _STRICT_PREFIX_PROVIDERS:
        return None
    expected = "zai" if provider == "zhipuai" else provider
    if first == expected:
        return None
    if provider == "zhipuai":
        return f"上游模型 ID 前缀应为 zai/…（智谱 LiteLLM 标识），当前为 {first}/…"
    return f"上游模型 ID 前缀应为 {expected}/…，当前为 {first}/…"


__all__ = ["litellm_prefix_violation_message"]
