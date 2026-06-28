"""Gateway rollup watermark（单行表）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.database import Base

_ROLLUP_STATE_SINGLETON_ID = 1


class GatewayRollupState(Base):
    """记录 ``gateway_metrics_hourly`` 增量 rollup 水位。"""

    __tablename__ = "gateway_rollup_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_gateway_rollup_state_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=_ROLLUP_STATE_SINGLETON_ID)
    last_rolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["_ROLLUP_STATE_SINGLETON_ID", "GatewayRollupState"]
