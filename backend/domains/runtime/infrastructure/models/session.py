"""
Session Model - 会话模型
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.infrastructure.orm.base import BaseModel

if TYPE_CHECKING:
    from domains.agent_catalog.infrastructure.models.agent import Agent
    from domains.identity.infrastructure.models.user import User
    from domains.runtime.infrastructure.models.message import Message


class Session(BaseModel):
    """会话模型"""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    anonymous_user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="匿名用户ID，用于未登录用户的会话",
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
        foreign_keys=[user_id],
    )
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="sessions",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Session {self.title}>"
