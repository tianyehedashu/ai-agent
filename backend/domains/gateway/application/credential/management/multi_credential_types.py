"""多凭据一键注册返回类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute


@dataclass(frozen=True)
class MultiCredentialGatewayModelResult:
    route: GatewayRoute
    models: list[GatewayModel]


__all__ = ["MultiCredentialGatewayModelResult"]
