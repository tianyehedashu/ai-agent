"""上游 OpenAI 兼容 ``/v1/models`` 列举 URL 策略（无 I/O）。"""

from __future__ import annotations

from typing import Literal

_ANTHROPIC_UNSUPPORTED = "Anthropic 不提供 OpenAI 兼容的 /v1/models 列举；请手填模型 ID，或使用带 OpenAI 兼容列表端点的代理。"


def resolve_openai_compatible_models_list_url(
    *, provider: str, api_base: str | None
) -> tuple[Literal["ok", "unsupported"], str | None, str | None]:
    """解析用于列举模型的 URL。

    Returns:
        ``(status, list_url, reason)`` — ``reason`` 仅在 ``unsupported`` 时非空。
    """
    p = provider.lower().strip()
    base = (api_base or "").strip() or None

    if p == "anthropic":
        return ("unsupported", None, _ANTHROPIC_UNSUPPORTED)

    if p == "openai":
        root = base.rstrip("/") if base else "https://api.openai.com/v1"
        return ("ok", f"{root}/models", None)

    if p == "custom":
        if not base:
            return ("unsupported", None, "custom 提供商需配置 api_base 后才能探测上游模型列表。")
        return ("ok", f"{base.rstrip('/')}/models", None)

    if p == "deepseek":
        root = base.rstrip("/") if base else "https://api.deepseek.com/v1"
        return ("ok", f"{root}/models", None)

    if p in ("dashscope", "zhipuai", "volcengine"):
        if not base:
            return (
                "unsupported",
                None,
                f"提供商「{p}」未配置 api_base 时无法在网关内发起 OpenAI 兼容的模型列表请求；"
                "请填写 api_base 后重试，或直接手填模型 ID。",
            )
        return ("ok", f"{base.rstrip('/')}/models", None)

    if base:
        return ("ok", f"{base.rstrip('/')}/models", None)
    return (
        "unsupported",
        None,
        f"提供商「{p}」未配置 api_base，且网关未内置其官方列举端点；请配置 api_base 或手填模型 ID。",
    )


__all__ = ["resolve_openai_compatible_models_list_url"]
