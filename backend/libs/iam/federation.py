"""联邦身份抽象：与具体协议（OIDC、introspection、SAML 等）解耦。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
import uuid


@runtime_checkable
class FederatedIdentityAdapterPort(Protocol):
    """外部身份源适配器占位；验签与拉元数据由各实现完成。"""

    async def verify_and_extract_subject(
        self,
        raw_token: str,
    ) -> tuple[uuid.UUID | None, str | None]:
        """返回 (internal_user_id_or_none, external_subject) 等扩展字段由 claims 映射层处理。"""


def federation_is_active(settings: object) -> bool:
    """是否启用任一外部联邦模式（含兼容：仅配置 oidc_issuer_url）。"""
    mode = getattr(settings, "federation_mode", "none")
    oidc_url = getattr(settings, "oidc_issuer_url", None)
    intro_url = getattr(settings, "oauth2_introspection_url", None)
    if mode == "oidc":
        return bool(oidc_url)
    if mode == "oauth2_introspection":
        return bool(intro_url)
    return bool(oidc_url)


__all__ = ["FederatedIdentityAdapterPort", "federation_is_active"]
