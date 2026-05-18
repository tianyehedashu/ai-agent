"""ProviderPlan / ProviderPlanQuota - 上游套餐（厂商订阅 / 预付费包）

业务语义：
- 我们对厂商（OpenAI / Anthropic / DashScope 等）购买的订阅或预付费包；
- 绑到 ``provider_credentials`` + 可选 ``real_model``：``real_model`` 为 NULL 表示
  整凭据共享；非空表示按厂商模型粒度（OpenAI RPD / DashScope 子包）。
- 在套餐有效期内含 1~N 条 ``provider_plan_quotas``（5h / 7d / 30d / total 等
  滚动窗口），任一桶耗尽即视为该 deployment 暂时不可用 → LiteLLM Router 触发
  cooldown，切下条凭据 / fallback 模型；与下游 EntitlementPlan 严格分离。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class ProviderPlan(BaseModel):
    """上游套餐头：绑 (credential, real_model?)，含起止与续期标志。"""

    __tablename__ = "provider_plans"

    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_credentials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    real_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="厂商模型字符串；NULL 表示该凭据下所有模型共享此套餐",
    )
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="UI 显示名，如 'Claude Pro 月套餐'",
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
        comment="到期后是否按相同窗口自动顺延创建下一段",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="订阅 ID / order ref / cost_basis_usd 等",
    )

    __table_args__ = (
        Index(
            "ix_provider_plans_active",
            "credential_id",
            "real_model",
            "is_active",
            "valid_from",
            "valid_until",
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderPlan {self.label} cred={self.credential_id} rm={self.real_model!r}>"


class ProviderPlanQuota(BaseModel):
    """上游套餐内的单层滚动配额桶。

    与 ``EntitlementPlanQuota`` 形态对称，但通过键空间 ``ns="provider"`` 在 Redis 中隔离。
    """

    __tablename__ = "provider_plan_quotas"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="桶 label，例：'5h' / 'weekly' / 'monthly' / 'total'",
    )
    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="滚动窗口长度（秒）；0 表示整套餐有效期作为一个桶",
    )
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("plan_id", "label", name="uq_provider_plan_quota_label"),)

    def __repr__(self) -> str:
        return (
            f"<ProviderPlanQuota plan={self.plan_id} {self.label} "
            f"win={self.window_seconds}s>"
        )


__all__ = ["ProviderPlan", "ProviderPlanQuota"]
