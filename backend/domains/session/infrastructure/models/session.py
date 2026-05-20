"""
Session Model - 会话模型
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, TenantScopedMixin

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.agent import Agent
    from domains.agent.infrastructure.models.message import Message
    from domains.agent.infrastructure.models.video_gen_task import VideoGenTask


class Session(BaseModel, TenantScopedMixin):
    """会话模型（归属 ``tenant_id``：注册用户 personal team 或匿名 shadow user team）。"""

    __tablename__ = "sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
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
    video_task_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="视频任务数量",
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
    video_tasks: Mapped[list["VideoGenTask"]] = relationship(
        "VideoGenTask",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Session {self.title}>"
