"""
Memory Model - 记忆模型
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.user import User


class Memory(BaseModel):
    """记忆模型"""

    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        name="memory_type",
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )
    access_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memories",
    )

    def __repr__(self) -> str:
        return f"<Memory {self.type}: {self.content[:50]}...>"
