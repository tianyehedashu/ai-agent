"""
Message Model - 消息模型
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.session import Session


class Message(BaseModel):
    """消息模型"""

    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    tool_calls: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    tool_call_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    extra_data: Mapped[dict] = mapped_column(
        JSONB,
        name="metadata",
        default=dict,
        nullable=False,
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # 关系
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message {self.role}: {self.content[:50] if self.content else ''}...>"
