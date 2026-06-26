"""上下游套餐配额窗口用量汇总（展示读路径，callback 异步 upsert）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from sqlalchemy import BigInteger, DateTime, Numeric, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.database import Base


class GatewayQuotaPlanUsageBucket(Base):
    """按 (ns, plan, quota, window_start) 累计用量。"""

    __tablename__ = "gateway_quota_plan_usage_buckets"

    ns: Mapped[str] = mapped_column(String(16), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quota_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    requests: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    images: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 6), nullable=False, server_default="0", default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (PrimaryKeyConstraint("ns", "plan_id", "quota_id", "window_start"),)


__all__ = ["GatewayQuotaPlanUsageBucket"]
