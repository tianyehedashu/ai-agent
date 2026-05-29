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
    from domains.agent.infrastructure.models.memory import Memory


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
    vendor_creator_id: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="厂商系统操作用户 ID（如 GIIKIN creator_id）",
    )
    giikin_user_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
        comment="giikin 单点登录用户 ID（SSO 模式下经 HiGress 注入，JIT 映射键）",
    )

    memories: Mapped[list["Memory"]] = relationship(
        "Memory",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
        primaryjoin="Memory.user_id == User.id",
        foreign_keys="Memory.user_id",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
