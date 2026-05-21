"""
Agent Model - Agent 模型
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, TenantScopedMixin

if TYPE_CHECKING:
    from domains.session.infrastructure.models.session import Session


class Agent(BaseModel, TenantScopedMixin):
    """Agent 模型（归属 personal / shared team 的 ``tenant_id``）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "agents"

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
        default="claude-3-5-sonnet",  # Gateway catalog id
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

    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="agent",
        primaryjoin="Session.agent_id == Agent.id",
        foreign_keys="Session.agent_id",
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name}>"
