"""GatewayResourceGrant - 个人 BYOK 凭据/模型对协作团队的共享授权（Share-not-Copy）。"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayResourceGrant(BaseModel):
    """个人资源授权：subject 指向 user-scope 凭据或 personal team 模型；target 为协作团队。"""

    __tablename__ = "gateway_resource_grants"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="资源拥有者 users.id",
    )
    subject_kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="credential | model",
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="provider_credentials.id 或 gateway_models.id",
    )
    target_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="被授权协作团队 gateway_teams.id",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="创建/更新 grant 的操作者 user_id",
    )

    __table_args__ = (
        UniqueConstraint(
            "subject_kind",
            "subject_id",
            "target_team_id",
            name="uq_gateway_resource_grants_subject_target",
        ),
        Index(
            "ix_gateway_resource_grants_target_enabled",
            "target_team_id",
            "enabled",
        ),
        Index(
            "ix_gateway_resource_grants_subject",
            "subject_kind",
            "subject_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<GatewayResourceGrant {self.subject_kind}={self.subject_id} "
            f"→ team={self.target_team_id} owner={self.owner_user_id}>"
        )


__all__ = ["GatewayResourceGrant"]
