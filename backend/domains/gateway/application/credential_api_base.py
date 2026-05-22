"""管理面创建凭据时 api_base 默认值解析（application 辅助）。"""

from __future__ import annotations

from domains.gateway.domain.provider_api_base import resolve_effective_api_base


def resolve_credential_api_base_for_create(provider: str, api_base: str | None) -> str | None:
    """创建凭据时：显式 base 优先，否则 ``get_default_api_base``。"""
    return resolve_effective_api_base(provider, api_base)


__all__ = ["resolve_credential_api_base_for_create"]
