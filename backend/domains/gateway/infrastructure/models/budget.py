"""
GatewayBudget - 预算配置与当前用量

取代旧的 UserQuota，支持四级 target_kind（system / tenant / key / user）和三种 period。
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class GatewayBudget(BaseModel):
    """预算配置

    业务规则：
    - target_kind: system / tenant / key / user
    - period: daily / monthly / total
    - 同 target_kind + target_id + period + model_name 语义唯一（汇总行 model_name IS NULL）
    - limit_* NULL 表示该维度无限制
    """

    __tablename__ = "gateway_budgets"

    target_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 限额
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    soft_limit_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="软限额：达阈值告警但不阻断（对齐 LiteLLM soft_budget）",
    )
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_parallel_requests: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="并发上限",
    )

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
    budget_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次预算重置时刻（显式，便于 UI 展示）",
    )

    __table_args__ = (
        Index(
            "uq_gateway_budgets_target_period_agg",
            "target_kind",
            "target_id",
            "period",
            unique=True,
            postgresql_where=text("model_name IS NULL"),
        ),
        Index(
            "uq_gateway_budgets_target_period_model",
            "target_kind",
            "target_id",
            "period",
            "model_name",
            unique=True,
            postgresql_where=text("model_name IS NOT NULL"),
        ),
        Index("ix_gateway_budgets_target_lookup", "target_kind", "target_id"),
    )

    def __repr__(self) -> str:
        m = self.model_name or "*"
        return f"<GatewayBudget {self.target_kind}:{self.target_id} {self.period} model={m!r}>"


__all__ = ["GatewayBudget"]
