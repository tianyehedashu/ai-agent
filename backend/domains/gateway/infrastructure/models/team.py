"""
Team / TeamMember Models - 团队与成员

每个用户注册时自动创建 personal team；用户也可创建 shared team 邀请他人加入。
"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class Team(BaseModel):
    """团队

    Attributes:
        kind: personal / shared
        owner_user_id: 团队所有者 ID
        slug: URL 友好标识（同一所有者下唯一）
        settings: 团队级默认设置（如默认 routing_strategy、default guardrail）
    """

    __tablename__ = "gateway_teams"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="团队展示名")
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="shared",
        comment="personal / shared",
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("owner_user_id", "slug", name="uq_gateway_teams_owner_slug"),
    )

    def __repr__(self) -> str:
        return f"<Team {self.id} {self.name} ({self.kind})>"


class TeamMember(BaseModel):
    """团队成员"""

    __tablename__ = "gateway_team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="owner / admin / member",
    )

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_gateway_team_members"),
        Index("ix_gateway_team_members_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TeamMember team={self.team_id} user={self.user_id} role={self.role}>"


__all__ = ["Team", "TeamMember"]
