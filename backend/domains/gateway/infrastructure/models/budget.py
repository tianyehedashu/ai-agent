"""
GatewayBudget - 预算配置与当前用量

取代旧的 UserQuota，支持四级 target_kind（system / tenant / key / user）和三种 period。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Boolean,
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

# 成员总量/模型护栏行唯一索引中 tenant_id 为 NULL 时的占位 UUID（非 user 维度恒用此值）。
_TENANT_SENTINEL = "00000000-0000-0000-0000-000000000000"


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
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment=(
            "仅 target_kind=user 且 credential_id IS NULL 时非空：成员总量/模型护栏所属团队"
            "（按团队隔离成员额度）；其余维度为 NULL（refs gateway_teams.id，无 DB FK）"
        ),
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 启用停用 + 起止时间（按行/规则维度，热路径据此纳入或跳过执法）
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        default=True,
        comment="停用时该预算行不参与热路径执法",
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效起（含）；NULL 表示不限",
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效止（不含）；NULL 表示不限",
    )
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="非空表示「成员+凭据(+模型)」专属预算；仅与 target_kind=user 组合（refs provider_credentials.id，无 DB FK）",
    )

    # 限额
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    soft_limit_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="已废弃：代理热路径不读取；写入时忽略，请使用 limit_usd",
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
    period_timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="UTC",
        default="UTC",
        comment="IANA 时区；日历日/月切本地时刻",
    )
    period_reset_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
        comment="本地日切时刻：自 00:00 起的分钟数 0..1439",
    )
    period_reset_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        default=1,
        comment="月切日 1..31；短月按月末 clamp",
    )

    __table_args__ = (
        # 成员总量/模型护栏行（credential_id IS NULL）按 tenant 隔离：
        # 用 COALESCE(tenant_id, 全零 UUID) 使非 user 维度（tenant_id 恒 NULL）仍保持原唯一性，
        # 同一成员在不同团队的护栏行可并存。
        Index(
            "uq_gateway_budgets_target_period_agg",
            "target_kind",
            "target_id",
            text(f"coalesce(tenant_id, '{_TENANT_SENTINEL}'::uuid)"),
            "period",
            unique=True,
            postgresql_where=text("model_name IS NULL AND credential_id IS NULL"),
        ),
        Index(
            "uq_gateway_budgets_target_period_model",
            "target_kind",
            "target_id",
            text(f"coalesce(tenant_id, '{_TENANT_SENTINEL}'::uuid)"),
            "period",
            "model_name",
            unique=True,
            postgresql_where=text("model_name IS NOT NULL AND credential_id IS NULL"),
        ),
        Index(
            "uq_gateway_budgets_target_period_cred_agg",
            "target_kind",
            "target_id",
            "period",
            "credential_id",
            unique=True,
            postgresql_where=text("model_name IS NULL AND credential_id IS NOT NULL"),
        ),
        Index(
            "uq_gateway_budgets_target_period_cred_model",
            "target_kind",
            "target_id",
            "period",
            "credential_id",
            "model_name",
            unique=True,
            postgresql_where=text("model_name IS NOT NULL AND credential_id IS NOT NULL"),
        ),
        Index("ix_gateway_budgets_target_lookup", "target_kind", "target_id"),
    )

    def __repr__(self) -> str:
        m = self.model_name or "*"
        return f"<GatewayBudget {self.target_kind}:{self.target_id} {self.period} model={m!r}>"


__all__ = ["GatewayBudget"]
