"""LiteLLM Router ``get_model_info`` 价目表键与 deployment 注册条目（纯函数）。

Gateway 大量火山自定义模型（``doubao-seed-*`` / ``ep-*``）不在 LiteLLM 内置
``model_cost`` 中。``enable_pre_call_checks=True`` 时，Router 对每个 deployment 调
``get_router_model_info`` → ``litellm.get_model_info``，未映射即抛 ``This model isn't
mapped yet`` 并被上层 catch 后以富文本 traceback 同步打印——大路由池下每请求渲染
数十条堆栈，阻塞事件循环。把 deployment 涉及的模型注册进 ``model_cost`` 即从根上消除
该异常，同时让上下文窗口检查与成本归因生效。
"""

from __future__ import annotations

from typing import Any

# capability → LiteLLM ``ModelInfo.mode``（无对应者省略，仅作元数据，不影响"是否映射"判定）
_CAPABILITY_TO_LITELLM_MODE: dict[str, str] = {
    "chat": "chat",
    "embedding": "embedding",
    "image": "image_generation",
    "audio_transcription": "audio_transcription",
    "audio_speech": "audio_speech",
    "rerank": "rerank",
    "moderation": "moderation",
}

_OPTIONAL_COST_KEYS: tuple[str, ...] = (
    "cache_creation_input_token_cost",
    "cache_read_input_token_cost",
)


def litellm_model_info_lookup_key(
    *,
    model: str,
    custom_llm_provider: str | None,
) -> str:
    """与 LiteLLM Router ``get_router_model_info`` 一致的 ``model_cost`` 键。"""
    cleaned = (model or "").strip()
    if not cleaned:
        return ""
    provider = (custom_llm_provider or "").strip().lower()
    if provider and not cleaned.lower().startswith(f"{provider}/"):
        return f"{provider}/{cleaned}"
    return cleaned


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value.is_integer() and value > 0:
        return int(value)
    return None


def _coerce_cost(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


def registry_entry_from_deployment(
    *,
    litellm_params: dict[str, Any],
    model_info: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """由 Router deployment 行构造 ``litellm.register_model`` 条目。

    ``max_input_tokens`` 仅在已知（来自模型 ``tags.context_window``）时写入；未知则省略，
    让 pre_call 跳过上下文窗口过滤，避免用臆造上限误杀大上下文模型的部署。
    """
    raw_provider = litellm_params.get("custom_llm_provider")
    provider = str(raw_provider).strip() if raw_provider is not None else None
    key = litellm_model_info_lookup_key(
        model=str(litellm_params.get("model") or ""),
        custom_llm_provider=provider,
    )
    if not key:
        return None

    entry: dict[str, Any] = {
        "input_cost_per_token": _coerce_cost(litellm_params.get("input_cost_per_token")) or 0.0,
        "output_cost_per_token": _coerce_cost(litellm_params.get("output_cost_per_token")) or 0.0,
    }
    if provider:
        entry["litellm_provider"] = provider.lower()

    capability = model_info.get("capability")
    mode = _CAPABILITY_TO_LITELLM_MODE.get(str(capability)) if capability is not None else None
    if mode is not None:
        entry["mode"] = mode

    max_input_tokens = _coerce_positive_int(model_info.get("max_input_tokens"))
    if max_input_tokens is not None:
        entry["max_input_tokens"] = max_input_tokens
        entry["max_tokens"] = max_input_tokens

    for cost_key in _OPTIONAL_COST_KEYS:
        cost = _coerce_cost(litellm_params.get(cost_key))
        if cost is not None:
            entry[cost_key] = cost
    return key, entry


def collect_registry_payload_from_deployments(
    deployments: list[dict[str, Any]],
    *,
    existing_keys: frozenset[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """从 deployment 列表收集待注册价目；``existing_keys`` 命中则跳过（不覆盖内置映射）。"""
    known = existing_keys or frozenset()
    payload: dict[str, dict[str, Any]] = {}
    for dep in deployments:
        litellm_params = dep.get("litellm_params")
        model_info = dep.get("model_info")
        if not isinstance(litellm_params, dict) or not isinstance(model_info, dict):
            continue
        built = registry_entry_from_deployment(
            litellm_params=litellm_params,
            model_info=model_info,
        )
        if built is None:
            continue
        key, entry = built
        if key in known or key in payload:
            continue
        payload[key] = entry
    return payload


__all__ = [
    "collect_registry_payload_from_deployments",
    "litellm_model_info_lookup_key",
    "registry_entry_from_deployment",
]
