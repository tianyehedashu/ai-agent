"""
GatewayRoute - 路由配置（含三类 fallback）

把"虚拟模型名"路由到 GatewayModel 列表（主备 + 三类 fallback）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ARRAY, Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class GatewayRoute(BaseModel, TenantScopedMixin):
    """路由配置（仅租户行；系统级见 ``system_gateway_routes``）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "gateway_routes"

    virtual_model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    primary_models: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_general: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_content_policy: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    fallbacks_context_window: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, server_default="{}"
    )
    strategy: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default="simple-shuffle",
        comment=(
            "simple-shuffle / least-busy / latency-based-routing /"
            " usage-based-routing-v2 / cost-based-routing"
        ),
    )
    retry_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "virtual_model", name="uq_gateway_routes_tenant_virtual_model"
        ),
    )

    def __repr__(self) -> str:
        return f"<GatewayRoute {self.virtual_model} tenant={self.tenant_id}>"


__all__ = ["GatewayRoute"]
