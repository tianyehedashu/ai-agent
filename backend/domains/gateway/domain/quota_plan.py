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
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    import uuid

QuotaPlanNamespace = Literal["entitlement", "provider"]
ENTITLEMENT_NS: Final[QuotaPlanNamespace] = "entitlement"
PROVIDER_NS: Final[QuotaPlanNamespace] = "provider"

ExhaustedReason = Literal["usd", "tokens", "requests"]

# =============================================================================
# 周期重置策略 - 解决 "本地滚动窗口 vs 厂商日历重置" 的对齐偏差
# =============================================================================
#
# - rolling: 默认；按 ``window_seconds`` 滚动分钟桶（与原行为一致）。
# - calendar_daily_utc: 每日 UTC 00:00 重置（OpenAI/Anthropic/Google 通常如此）。
# - calendar_monthly_utc: 自然月 1 号 UTC 00:00 重置（月套餐）。
# - plan_anniversary: 从 ``valid_from`` 起每 ``window_seconds`` 切一段，与厂商
#   订阅锚点对齐（用户合同日不在自然边界上时使用）。
ResetStrategy = Literal[
    "rolling",
    "calendar_daily_utc",
    "calendar_monthly_utc",
    "plan_anniversary",
]
RESET_STRATEGY_DEFAULT: Final[ResetStrategy] = "rolling"


@dataclass(frozen=True)
class PlanQuotaSpec:
    """套餐内单层桶的纯值对象。

    Attributes:
        quota_id: 仓储行主键，用于 Redis key 唯一性。
        label: UI / 错误文案使用的桶名（"5h" / "weekly" / "total"）。
        window_seconds: 窗口长度（秒）；``0`` 表示「整套餐有效期作为一个桶」（=
            走 plan-level TTL，不做"分钟桶滚动")，由调用方按 plan.valid_until 处理。
        reset_strategy: 见 ``ResetStrategy``；默认 ``rolling``，与历史行为一致。
        plan_valid_from: ``plan_anniversary`` 策略所需的锚点；其他策略可缺省。
        limit_*: 任意一项可为 ``None`` 表示该维度不限。任一非空维度耗尽即整桶耗尽。
    """

    quota_id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    reset_strategy: ResetStrategy = RESET_STRATEGY_DEFAULT
    plan_valid_from: datetime | None = None

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
        """已耗尽时返回下一次重置时刻。

        - ``rolling``：``floor_min(earliest) * 60 + window_seconds``（最早桶到期）。
        - ``calendar_daily_utc``：当前 UTC 日的次日 00:00。
        - ``calendar_monthly_utc``：当前 UTC 月的下月 1 号 00:00。
        - ``plan_anniversary``：``valid_from + ceil((now-valid_from)/window) * window``。
        - ``window_seconds == 0``：返回 ``None``，由调用方查 plan.valid_until。
        """
        when = now or datetime.now(UTC)
        return compute_reset_at(
            strategy=self.spec.reset_strategy,
            window_seconds=self.spec.window_seconds,
            now=when,
            earliest_minute_in_window=self.earliest_minute_in_window,
            plan_valid_from=self.spec.plan_valid_from,
        )


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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _calendar_daily_utc_start(now: datetime) -> datetime:
    now = _as_utc(now)
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


def _calendar_monthly_utc_start(now: datetime) -> datetime:
    now = _as_utc(now)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def _calendar_daily_utc_end(now: datetime) -> datetime:
    return _calendar_daily_utc_start(now) + timedelta(days=1)


def _calendar_monthly_utc_end(now: datetime) -> datetime:
    start = _calendar_monthly_utc_start(now)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def _anniversary_segment_bounds(
    now: datetime, *, valid_from: datetime, window_seconds: int
) -> tuple[datetime, datetime]:
    """以 valid_from 为锚点切片。``now`` 落入第 k 段：[from + k*win, from + (k+1)*win)。"""
    now = _as_utc(now)
    valid_from = _as_utc(valid_from)
    if window_seconds <= 0:
        return valid_from, valid_from
    elapsed = (now - valid_from).total_seconds()
    k = int(elapsed // window_seconds)
    if k < 0:
        k = 0
    seg_start = valid_from + timedelta(seconds=k * window_seconds)
    seg_end = valid_from + timedelta(seconds=(k + 1) * window_seconds)
    return seg_start, seg_end


def compute_window_start_minute(
    now: datetime,
    window_seconds: int,
    *,
    strategy: ResetStrategy = RESET_STRATEGY_DEFAULT,
    plan_valid_from: datetime | None = None,
) -> int:
    """根据策略返回当前窗口的"最早有效分钟索引"（含）。

    - ``rolling``：``minute(now) - window_seconds//60``（与历史一致）。
    - ``calendar_daily_utc`` / ``calendar_monthly_utc``：当前自然日/月起点。
    - ``plan_anniversary``：当前段起点（依 ``plan_valid_from``）。
    - ``window_seconds == 0``：返回 0（累计计量，调用方按 plan TTL 处理）。
    """
    if window_seconds <= 0:
        return 0
    if strategy == "calendar_daily_utc":
        return compute_minute_index(_calendar_daily_utc_start(now))
    if strategy == "calendar_monthly_utc":
        return compute_minute_index(_calendar_monthly_utc_start(now))
    if strategy == "plan_anniversary":
        if plan_valid_from is None:
            return compute_minute_index(now - timedelta(seconds=window_seconds))
        seg_start, _ = _anniversary_segment_bounds(
            now, valid_from=plan_valid_from, window_seconds=window_seconds
        )
        return compute_minute_index(seg_start)
    return compute_minute_index(now - timedelta(seconds=window_seconds))


def compute_reset_at(
    *,
    strategy: ResetStrategy,
    window_seconds: int,
    now: datetime,
    earliest_minute_in_window: int | None = None,
    plan_valid_from: datetime | None = None,
) -> datetime | None:
    """统一的下次重置时刻计算；与 ``compute_window_start_minute`` 对偶。"""
    if window_seconds <= 0:
        return None
    if strategy == "calendar_daily_utc":
        return _calendar_daily_utc_end(now)
    if strategy == "calendar_monthly_utc":
        return _calendar_monthly_utc_end(now)
    if strategy == "plan_anniversary" and plan_valid_from is not None:
        _, seg_end = _anniversary_segment_bounds(
            now, valid_from=plan_valid_from, window_seconds=window_seconds
        )
        return seg_end
    if earliest_minute_in_window is None:
        return now
    earliest_dt = datetime.fromtimestamp(earliest_minute_in_window * 60, tz=UTC)
    return earliest_dt + timedelta(seconds=window_seconds)


__all__ = [
    "ENTITLEMENT_NS",
    "PROVIDER_NS",
    "RESET_STRATEGY_DEFAULT",
    "ExhaustedReason",
    "PlanQuotaSnapshot",
    "PlanQuotaSpec",
    "QuotaPlanCheckResult",
    "QuotaPlanNamespace",
    "QuotaPlanReservation",
    "ResetStrategy",
    "compute_minute_index",
    "compute_reset_at",
    "compute_window_start_minute",
]
