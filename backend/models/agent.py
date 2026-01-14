"""
Agent Model - Agent 模型
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.session import Session
    from models.user import User


class Agent(BaseModel):
    """Agent 模型"""

    __tablename__ = "agents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        default="claude-3-5-sonnet-20241022",
        nullable=False,
    )
    tools: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
    )
    temperature: Mapped[float] = mapped_column(
        Float,
        default=0.7,
        nullable=False,
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        nullable=False,
    )
    max_iterations: Mapped[int] = mapped_column(
        Integer,
        default=20,
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="agents",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="agent",
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name}>"
