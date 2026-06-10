"""DownstreamModelPricing - 下游售价目录（global / team / entitlement_plan）"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class DownstreamModelPricing(BaseModel):
    """下游模型售价；``inheritance_strategy=mirror`` 时单价列必须为 NULL。"""

    __tablename__ = "downstream_model_pricing"

    scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="global | team | entitlement_plan",
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    gateway_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="refs gateway_models.id; NULL = 该 scope 内默认价 (no DB FK)",
    )

    input_cost_per_token: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    output_cost_per_token: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    cache_creation_input_token_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 10), nullable=True
    )
    cache_read_input_token_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 10), nullable=True
    )
    per_request_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    inheritance_strategy: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="manual",
        default="manual",
        comment="mirror | manual",
    )

    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, server_default="1", default=1)

    __table_args__ = (
        UniqueConstraint(
            "scope",
            "scope_id",
            "gateway_model_id",
            "effective_from",
            name="uq_downstream_model_pricing_natural",
        ),
        Index(
            "ix_downstream_model_pricing_lookup",
            "scope",
            "scope_id",
            "gateway_model_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "ix_downstream_model_pricing_lookup_active",
            "scope",
            "scope_id",
            "gateway_model_id",
            "effective_from",
            postgresql_where=effective_to.is_(None),
        ),
        CheckConstraint(
            "(inheritance_strategy = 'manual' AND input_cost_per_token IS NOT NULL "
            "AND output_cost_per_token IS NOT NULL) OR "
            "(inheritance_strategy = 'mirror' AND input_cost_per_token IS NULL "
            "AND output_cost_per_token IS NULL "
            "AND cache_creation_input_token_cost IS NULL "
            "AND cache_read_input_token_cost IS NULL)",
            name="ck_downstream_pricing_strategy_columns",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DownstreamModelPricing {self.scope}:{self.scope_id} "
            f"model={self.gateway_model_id} {self.inheritance_strategy}>"
        )


__all__ = ["DownstreamModelPricing"]
