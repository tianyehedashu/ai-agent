"""
GatewayRouteTeamGrant Model - 路由跨团队共享授权

把一条个人路由（``GatewayRoute``，仍归 owner 的 personal team）发布给某个 shared team T，
让 T 的成员把它当普通模型（暴露别名）调用。调用以路由 owner 身份委派解析底层模型与凭据。

与 ``gateway_virtual_key_team_grants`` 对称：无 DB FK、软撤销、``is_active`` 上的部分唯一索引。
差异：路由 grant 目标永远是 owner 所在的 **其他** team，不存在自洽行（无 ``is_self``）。
"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import Boolean, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayRouteTeamGrant(BaseModel):
    """路由跨团队共享授权行

    业务规则：
    - 每个 (route_id, tenant_id) 至多一行 active grant
    - 每个 (tenant_id, exposed_alias) 至多一行 active grant（T 内调用名唯一）
    - 撤销为软删除（is_active=FALSE + revoked_at/reason）
    - ``tenant_id`` 语义为"被授权的消费 team T"而非归属，故不继承 TenantScopedMixin
    """

    __tablename__ = "gateway_route_team_grants"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs gateway_routes.id (no DB FK)",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="被授权消费 team T (refs teams.id, no DB FK)",
    )

    exposed_alias: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="T 内调用名（默认=route.virtual_model，可改；T 内唯一）",
    )

    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="= route.created_by_user_id（守恒）；成员移除时按此撤销",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="owner_revoked | team_admin_revoked | membership_lost | team_archived | route_deleted",
    )

    __table_args__ = (
        Index(
            "uq_route_team_grants_active",
            "route_id",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "uq_route_team_grants_alias_active",
            "tenant_id",
            "exposed_alias",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "ix_route_team_grants_tenant_active",
            "tenant_id",
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "ix_route_team_grants_route_active",
            "route_id",
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "ix_route_team_grants_user_tenant_active",
            "granted_by_user_id",
            "tenant_id",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    def revoke(self, reason: str) -> None:
        """软撤销本行"""
        self.is_active = False
        self.revoked_at = datetime.now(UTC)
        self.revoked_reason = reason

    def __repr__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"<RouteTeamGrant route={self.route_id} team={self.tenant_id} {status}>"


__all__ = ["GatewayRouteTeamGrant"]
