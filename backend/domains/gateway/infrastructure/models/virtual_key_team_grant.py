"""
GatewayVirtualKeyTeamGrant Model - 虚拟 Key 跨团队授权

一把 vkey 可授权访问多个 team 的模型；
主属 team 自洽行 (is_self=TRUE) 在回填时自动插入。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel

if TYPE_CHECKING:
    pass


class GatewayVirtualKeyTeamGrant(BaseModel):
    """虚拟 Key 跨团队授权行

    业务规则：
    - 每个 (vkey_id, tenant_id) 至多一行 active grant
    - is_self=TRUE 表示 vkey 主属 team 的自洽行（不可撤销、离线清理跳过）
    - 撤销为软删除（is_active=FALSE + revoked_at/reason）
    - 不继承 TenantScopedMixin（此表 tenant_id 语义为"被授权 team"而非"归属"）
    """

    __tablename__ = "gateway_virtual_key_team_grants"

    vkey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs gateway_virtual_keys.id (no DB FK)",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="被授权 team (refs teams.id, no DB FK)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="= vkey.created_by_user_id（守恒）",
    )

    is_self: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="自洽 grant（vkey 主属 team），离线清理跳过",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="owner_revoked | membership_lost | team_archived",
    )

    __table_args__ = (
        UniqueConstraint(
            "vkey_id",
            "tenant_id",
            name="uq_vkey_team_grants_active",
            postgresql_where="is_active = TRUE",
        ),
        Index(
            "ix_vkey_team_grants_vkey_active",
            "vkey_id",
            postgresql_where="is_active = TRUE",
        ),
        Index(
            "ix_vkey_team_grants_user_tenant_active",
            "granted_by_user_id",
            "tenant_id",
            postgresql_where="is_active = TRUE",
        ),
    )

    def revoke(self, reason: str) -> None:
        """软撤销本行"""
        self.is_active = False
        self.revoked_at = datetime.now(UTC)
        self.revoked_reason = reason

    def __repr__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"<VkeyTeamGrant vkey={self.vkey_id} team={self.tenant_id} {status}>"


__all__ = ["GatewayVirtualKeyTeamGrant"]
