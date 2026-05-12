"""
GatewayBudget - 预算配置与当前用量

取代旧的 UserQuota，支持四级 scope（system / team / key / user）和三种 period。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayBudget(BaseModel):
    """预算配置

    业务规则：
    - scope: system / team / key / user
    - period: daily / monthly / total
    - 同 scope + scope_id + period 唯一
    - limit_* NULL 表示该维度无限制
    """

    __tablename__ = "gateway_budgets"

    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)

    # 限额
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 当前用量
    current_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        server_default="0",
        default=Decimal("0"),
    )
    current_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    current_requests: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )

    # 重置
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "scope", "scope_id", "period", name="uq_gateway_budgets_scope_period"
        ),
        Index("ix_gateway_budgets_lookup", "scope", "scope_id"),
    )

    def __repr__(self) -> str:
        return f"<GatewayBudget {self.scope}:{self.scope_id} {self.period}>"


__all__ = ["GatewayBudget"]
