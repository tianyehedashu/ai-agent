"""UpstreamModelPricing - 上游成本目录（平台维护，对齐 LiteLLM model_prices_and_context_window）"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class UpstreamModelPricing(BaseModel):
    """上游模型单价；键名与 LiteLLM ``input_cost_per_token`` 等 1:1 对齐。"""

    __tablename__ = "upstream_model_pricing"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    upstream_model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default="chat",
        default="chat",
        comment="chat / embedding / image / video 等",
    )

    input_cost_per_token: Mapped[Decimal] = mapped_column(Numeric(14, 10), nullable=False)
    output_cost_per_token: Mapped[Decimal] = mapped_column(Numeric(14, 10), nullable=False)
    cache_creation_input_token_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 10), nullable=True
    )
    cache_read_input_token_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 10), nullable=True
    )

    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="LiteLLM 扩展键：input_cost_per_image、input_cost_per_token_above_X 等",
    )

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, server_default="1", default=1)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="manual",
        default="manual",
        comment="toml / manual / litellm_fallback",
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "upstream_model",
            "capability",
            "effective_from",
            name="uq_upstream_model_pricing_natural",
        ),
        Index(
            "ix_upstream_model_pricing_lookup",
            "provider",
            "upstream_model",
            "capability",
            "effective_from",
            "effective_to",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UpstreamModelPricing {self.provider}/{self.upstream_model} "
            f"cap={self.capability} v={self.version}>"
        )


__all__ = ["UpstreamModelPricing"]
