"""ProviderQuota - 上游配额规则（扁平：一行 = 一条规则）

业务语义：
- 绑 ``provider_credentials`` + 可选 ``real_model``（NULL = 整凭据共享）；
- 每条规则自带窗口、限额、启用停用与起止时间；
- 热路径执法按行过滤；计数键 ``plan_id = quota_id = id``（与平台预算约定一致）。
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class ProviderQuota(BaseModel):
    """上游配额规则：凭据 + 可选 real_model + label 唯一确定一行。"""

    __tablename__ = "provider_quotas"

    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="refs provider_credentials.id (no DB FK)",
    )
    real_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="厂商模型字符串；NULL 表示该凭据下所有模型共享此规则",
    )
    label: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="规则 label，例：'default' / 'daily' / 'monthly'",
    )
    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="窗口长度（秒）；0 表示累计额度",
    )
    reset_strategy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="rolling",
        server_default="rolling",
        comment="rolling | calendar_daily_utc | calendar_monthly_utc",
    )
    reset_timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="UTC",
        default="UTC",
    )
    reset_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )
    reset_day_of_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        default=1,
    )
    limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_images: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="图片生成张数限额（仅 image capability 路径有意义）",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        default=True,
        comment="停用时该规则不参与热路径执法",
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

    __table_args__ = (
        Index(
            "ix_provider_quotas_cred_model_enabled",
            "credential_id",
            "real_model",
            "enabled",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderQuota {self.label} cred={self.credential_id} "
            f"rm={self.real_model!r} win={self.window_seconds}s>"
        )


__all__ = ["ProviderQuota"]
