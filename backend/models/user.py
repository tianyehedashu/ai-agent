"""
User Model - 用户模型
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

# SQLAlchemy relationship 常量
CASCADE_DELETE_ORPHAN = "all, delete-orphan"

if TYPE_CHECKING:
    from models.agent import Agent
    from models.memory import Memory
    from models.session import Session


class User(BaseModel):
    """用户模型"""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )

    # 关系
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
    )
    memories: Mapped[list["Memory"]] = relationship(
        "Memory",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
