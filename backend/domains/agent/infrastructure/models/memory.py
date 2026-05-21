"""
Memory Model - 记忆模型
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, TenantScopedMixin

if TYPE_CHECKING:
    from domains.identity.infrastructure.models.user import User


class Memory(BaseModel, TenantScopedMixin):
    """记忆模型（归属 personal team tenant）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs users.id (no DB FK)",
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
    extra_data: Mapped[dict] = mapped_column(
        JSONB,
        name="metadata",
        default=dict,
        nullable=False,
    )
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="refs sessions.id (no DB FK)",
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
        primaryjoin="Memory.user_id == User.id",
        foreign_keys="Memory.user_id",
    )

    def __repr__(self) -> str:
        return f"<Memory {self.type}: {self.content[:50]}...>"
