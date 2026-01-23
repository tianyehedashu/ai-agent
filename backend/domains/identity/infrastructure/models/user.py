"""
User Model - 用户模型

兼容 FastAPI Users 的用户表结构。"""

from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db.database import Base
from libs.orm.base import TimestampMixin

# SQLAlchemy relationship 常量
CASCADE_DELETE_ORPHAN = "all, delete-orphan"

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.agent import Agent
    from domains.agent.infrastructure.models.memory import Memory
    from domains.agent.infrastructure.models.session import Session


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    """用户模型（FastAPI Users）"""

    __tablename__ = "users"

    # FastAPI Users base includes:
    # - id (UUID)
    # - email
    # - hashed_password
    # - is_active
    # - is_superuser
    # - is_verified

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
    role: Mapped[str] = mapped_column(
        String(50),
        default="user",
        server_default="user",
        nullable=False,
    )

    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
        foreign_keys="Session.user_id",  # 明确指定外键，避免与 anonymous_user_id 混淆
    )
    memories: Mapped[list["Memory"]] = relationship(
        "Memory",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
