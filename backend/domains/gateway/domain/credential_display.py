"""凭据展示用纯函数（掩码、api_base 回退，无 I/O）。"""

from __future__ import annotations

from domains.gateway.domain.provider_api_base import get_default_api_base


def mask_plain_secret_for_display(plain: str) -> str:
    """对 API Key 类字符串做展示用掩码（不回传明文）。"""
    s = plain.strip()
    if len(s) <= 8:
        return "••••"
    prefix = s[:4]
    suffix = s[-4:]
    return f"{prefix}…{suffix}"


def display_api_base_for_credential(
    *,
    provider: str,
    api_base: str | None,
    effective_openai: str | None,
) -> str | None:
    """列表/详情展示 endpoint：显式 api_base 优先，否则 provider 默认或 effective。"""
    if (api_base or "").strip():
        return api_base
    default = get_default_api_base(provider)
    if default:
        return default
    return effective_openai


__all__ = [
    "display_api_base_for_credential",
    "mask_plain_secret_for_display",
]
