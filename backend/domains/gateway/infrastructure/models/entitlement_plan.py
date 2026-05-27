"""EntitlementPlan / EntitlementPlanQuota - 下游套餐（卖给客户的额度）"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, PolicyTargetMixin


class EntitlementPlan(BaseModel, PolicyTargetMixin):
    """下游套餐头：target_kind ∈ {vkey, apikey_grant}，绑入站调用凭证。"""

    __tablename__ = "entitlement_plans"

    target_kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="挂载类型：vkey / apikey_grant",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="UI 显示名，如 'Pro 月套餐'",
    )
    included_models: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)),
        nullable=False,
        server_default="{}",
        comment="覆盖的虚拟模型名，空 = 全部",
    )
    included_capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)),
        nullable=False,
        server_default="{}",
        comment="覆盖的 capability，空 = 全部",
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "ix_entitlement_plans_active",
            "target_kind",
            "target_id",
            "is_active",
            "valid_from",
            "valid_until",
        ),
        Index(
            "ix_entitlement_plans_lifecycle",
            "valid_until",
            postgresql_where=text("is_active IS TRUE"),
        ),
    )

    def __repr__(self) -> str:
        return f"<EntitlementPlan {self.label} {self.target_kind}:{self.target_id}>"


class EntitlementPlanQuota(BaseModel):
    """下游套餐的单层滚动配额桶。"""

    __tablename__ = "entitlement_plan_quotas"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs entitlement_plans.id (no DB FK)",
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="窗口长度（秒）；0 表示整套餐有效期作为一个桶",
    )
    reset_strategy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="rolling",
        server_default="rolling",
        comment=(
            "重置策略：rolling（默认滚动）| calendar_daily_utc（每日 UTC 重置）|"
            " calendar_monthly_utc（每月 1 号 UTC 重置）| plan_anniversary（按 valid_from 切片）"
        ),
    )
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_usd_per_token: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8),
        nullable=True,
        comment="客户单价（如 $1/1Mtokens → 1e-6）；NULL 时统计 margin 时按上游 cost 等价记账",
    )
    unit_price_usd_per_request: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="按请求计价时的单价；与 unit_price_usd_per_token 互不冲突，分别累加",
    )

    __table_args__ = (UniqueConstraint("plan_id", "label", name="uq_entitlement_plan_quota_label"),)

    def __repr__(self) -> str:
        return f"<EntitlementPlanQuota plan={self.plan_id} {self.label} win={self.window_seconds}s>"


__all__ = ["EntitlementPlan", "EntitlementPlanQuota"]
