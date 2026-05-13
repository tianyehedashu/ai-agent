"""外部 IdP claims 映射（与验签协议解耦；联邦模式见 libs/iam/federation）。"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import uuid

from bootstrap.config import Settings


@dataclass(frozen=True)
class ExternalIdpClaimsView:
    """已通过签名校验的外部令牌 claims 的统一视图（便于网关消费）。"""

    subject: str
    tenant_id: uuid.UUID | None
    raw: dict[str, object]


def parse_external_idp_claims(claims: dict[str, object]) -> ExternalIdpClaimsView:
    """将标准或自定义 claims 规范化为内部视图。

    支持常见键：``tenant_id``、``org_id``（字符串 UUID）。
    调用方须保证 ``claims`` 已由对应联邦适配器完成完整性/签名校验。
    """
    sub = str(claims.get("sub", ""))
    tenant_raw = claims.get("tenant_id") if "tenant_id" in claims else claims.get("org_id")
    tenant_id: uuid.UUID | None = None
    if isinstance(tenant_raw, str):
        with contextlib.suppress(ValueError):
            tenant_id = uuid.UUID(tenant_raw)
    elif isinstance(tenant_raw, uuid.UUID):
        tenant_id = tenant_raw
    return ExternalIdpClaimsView(subject=sub, tenant_id=tenant_id, raw=dict(claims))


def external_idp_configured(settings: Settings) -> bool:
    """是否配置了可工作的外部身份联邦（兼容仅填 oidc_issuer_url）。"""
    from libs.iam.federation import federation_is_active

    return federation_is_active(settings)


__all__ = [
    "ExternalIdpClaimsView",
    "external_idp_configured",
    "parse_external_idp_claims",
]
