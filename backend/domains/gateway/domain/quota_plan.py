"""共享套餐配额值对象 - 上下游 (ProviderPlan / EntitlementPlan) 共用

- ``PlanQuotaSpec`` / ``PlanQuotaSnapshot``：纯值对象。
- ``QuotaPlanNamespace``：Redis 键空间（"entitlement" / "provider"），由
  ``QuotaPlanService`` 拼接键，确保上下游计量互不串扰。
- ``compute_minute_index`` 等纯函数：分钟分桶索引 / 窗口起点 / reset_at 计算。

不依赖任何 I/O 或 ORM。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal
import uuid

QuotaPlanNamespace = Literal["entitlement", "provider"]
ENTITLEMENT_NS: Final[QuotaPlanNamespace] = "entitlement"
PROVIDER_NS: Final[QuotaPlanNamespace] = "provider"

ExhaustedReason = Literal["usd", "tokens", "requests"]


@dataclass(frozen=True)
class PlanQuotaSpec:
    """套餐内单层滚动桶的纯值对象。

    Attributes:
        quota_id: 仓储行主键，用于 Redis key 唯一性。
        label: UI / 错误文案使用的桶名（"5h" / "weekly" / "total"）。
        window_seconds: 滚动窗口长度（秒）；``0`` 表示「整套餐有效期作为一个桶」（=
            走 plan-level TTL，不做"分钟桶滚动")，由调用方按 plan.valid_until 处理。
        limit_*: 任意一项可为 ``None`` 表示该维度不限。任一非空维度耗尽即整桶耗尽。
    """

    quota_id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None

    def has_any_limit(self) -> bool:
        return any(
            v is not None and v > 0
            for v in (self.limit_usd, self.limit_tokens, self.limit_requests)
        )


@dataclass(frozen=True)
class PlanQuotaSnapshot:
    """单层桶的当前用量快照。"""

    spec: PlanQuotaSpec
    used_usd: Decimal = Decimal("0")
    used_tokens: int = 0
    used_requests: int = 0
    exhausted_reason: ExhaustedReason | None = None
    earliest_minute_in_window: int | None = None

    @property
    def exhausted(self) -> bool:
        return self.exhausted_reason is not None

    def reset_at(self, now: datetime | None = None) -> datetime | None:
        """已耗尽时返回 "最早窗口内成员到期时刻"。

        滚动窗口语义：`reset_at = floor_min(earliest) * 60 + window_seconds`。
        当窗口为 0（整套餐期）时返回 ``None``，由调用方查 plan.valid_until。
        """
        if self.spec.window_seconds <= 0:
            return None
        if self.earliest_minute_in_window is None:
            return now or datetime.now(UTC)
        earliest_dt = datetime.fromtimestamp(
            self.earliest_minute_in_window * 60, tz=UTC
        )
        return earliest_dt + timedelta(seconds=self.spec.window_seconds)


@dataclass(frozen=True)
class QuotaPlanReservation:
    """单次预扣的还原标识（按 quota 一份），由调用方在失败时回滚。"""

    plan_id: uuid.UUID
    spec: PlanQuotaSpec
    minute_unix: int
    reserved_requests: int = 1


@dataclass
class QuotaPlanCheckResult:
    """``check_and_reserve`` 返回结构：成功为 reservations；失败包含耗尽快照。"""

    allowed: bool
    snapshots: list[PlanQuotaSnapshot] = field(default_factory=list)
    reservations: list[QuotaPlanReservation] = field(default_factory=list)
    exhausted_snapshot: PlanQuotaSnapshot | None = None


def compute_minute_index(when: datetime) -> int:
    """UNIX 时间戳除以 60 的整除值；供 Redis 分钟桶 key 与 zset score 使用。"""
    return int(when.timestamp() // 60)


def compute_window_start_minute(now: datetime, window_seconds: int) -> int:
    """``window_seconds=0`` 时返回 0（认为窗口起点是 epoch，即累计计量）。"""
    if window_seconds <= 0:
        return 0
    return compute_minute_index(now - timedelta(seconds=window_seconds))


__all__ = [
    "ENTITLEMENT_NS",
    "PROVIDER_NS",
    "ExhaustedReason",
    "PlanQuotaSnapshot",
    "PlanQuotaSpec",
    "QuotaPlanCheckResult",
    "QuotaPlanNamespace",
    "QuotaPlanReservation",
    "compute_minute_index",
    "compute_window_start_minute",
]
