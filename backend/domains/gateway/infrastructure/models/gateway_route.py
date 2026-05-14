"""
GatewayRoute - 路由配置（含三类 fallback）

把"虚拟模型名"路由到 GatewayModel 列表（主备 + 三类 fallback）。
"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import ARRAY, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayRoute(BaseModel):
    """路由配置

    业务规则：
    - virtual_model 是客户端使用的模型别名
    - team_id NULL 表示系统级路由（所有团队继承）
    - primary_models / fallbacks_* 存的是 GatewayModel.name 列表
    - strategy 对齐 LiteLLM Router 的 routing_strategy
    """

    __tablename__ = "gateway_routes"

    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
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
        UniqueConstraint("team_id", "virtual_model", name="uq_gateway_routes_team_virtual_model"),
    )

    def __repr__(self) -> str:
        return f"<GatewayRoute {self.virtual_model} team={self.team_id}>"


__all__ = ["GatewayRoute"]
