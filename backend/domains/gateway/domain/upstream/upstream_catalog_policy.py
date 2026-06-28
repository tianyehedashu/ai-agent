"""上游 OpenAI 兼容 ``/v1/models`` 列举 URL 策略（无 I/O）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .upstream_endpoint import resolve_upstream_endpoint
from .upstream_profile import ProbeStrategy
from .upstream_profile_registry import get_upstream_profile

if TYPE_CHECKING:
    from collections.abc import Mapping

_ANTHROPIC_UNSUPPORTED = (
    "Anthropic 不提供 OpenAI 兼容的 /v1/models 列举；请手填模型 ID，"
    "或使用带 OpenAI 兼容列表端点的代理。"
)


def resolve_openai_compatible_models_list_url(
    *,
    provider: str,
    api_base: str | None,
    profile_id: str | None = None,
    api_bases: Mapping[str, str] | None = None,
) -> tuple[Literal["ok", "unsupported"], str | None, str | None]:
    """解析用于列举模型的 URL。

    Returns:
        ``(status, list_url, reason)`` — ``reason`` 仅在 ``unsupported`` 时非空。
    """
    p = provider.lower().strip()
    profile = get_upstream_profile(profile_id, provider=p)

    if profile.probe_strategy == ProbeStrategy.NONE or not profile.probe_supported:
        reason = profile.probe_unsupported_reason or _ANTHROPIC_UNSUPPORTED
        return ("unsupported", None, reason)

    probe_protocol = profile.probe_protocol

    if p == "custom":
        endpoint = resolve_upstream_endpoint(
            provider=p,
            profile_id=profile_id,
            api_base=api_base,
            api_bases=api_bases,
            protocol=probe_protocol,
        )
        if not endpoint:
            return (
                "unsupported",
                None,
                "custom 提供商需配置 api_base 后才能探测上游模型列表。",
            )
        return ("ok", f"{endpoint.rstrip('/')}{profile.models_list_path}", None)

    endpoint = resolve_upstream_endpoint(
        provider=p,
        profile_id=profile_id,
        api_base=api_base,
        api_bases=api_bases,
        protocol=probe_protocol,
    )
    if not endpoint:
        return (
            "unsupported",
            None,
            f"提供商「{p}」未配置 api_base 时无法在网关内发起 OpenAI 兼容的模型列表请求；"
            "请填写 api_base 后重试，或直接手填模型 ID。",
        )
    return ("ok", f"{endpoint.rstrip('/')}{profile.models_list_path}", None)


def derive_client_facing_model_alias(upstream_model_id: str) -> str:
    """从上游 ``model`` id 派生客户端常用短别名（如 Claude Code / Cursor 请求名）。

    支持两种厂商快照命名：

    - Anthropic：``...-YYYYMMDD``（8 位日期紧贴产品名）
      - 例：``claude-sonnet-4-5-20250929`` → ``claude-sonnet-4-5``
    - OpenAI：``...-YYYY-MM-DD``（三段日期）
      - 例：``gpt-4o-2024-08-06`` → ``gpt-4o``

    其它（无识别日期后缀）原样返回，由运营手动覆盖。
    """
    raw = upstream_model_id.strip()
    if not raw:
        return raw

    parts = raw.split("-")

    # OpenAI 形：尾部三段 "YYYY-MM-DD"
    if _has_openai_trailing_date_suffix(parts):
        return "-".join(parts[:-3])

    # Anthropic 形：尾部一段 "YYYYMMDD"
    if len(parts) >= 2 and len(parts[-1]) == 8 and parts[-1].isdigit():
        return "-".join(parts[:-1])

    return raw


def _has_openai_trailing_date_suffix(parts: list[str]) -> bool:
    if len(parts) < 4:
        return False
    y, m, d = parts[-3], parts[-2], parts[-1]
    return (
        len(y) == 4 and y.isdigit() and len(m) == 2 and m.isdigit() and len(d) == 2 and d.isdigit()
    )


__all__ = [
    "derive_client_facing_model_alias",
    "resolve_openai_compatible_models_list_url",
]
