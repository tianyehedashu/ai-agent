"""共享套餐配额值对象 - 上下游 (ProviderQuota / EntitlementPlan) 共用

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
from typing import TYPE_CHECKING, Final, Literal, cast

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_period_window_start,
)
from domains.gateway.domain.period_reset_anchor import (
    compute_period_reset_at as _compute_platform_period_reset_at,
)

if TYPE_CHECKING:
    import uuid

QuotaPlanNamespace = Literal["entitlement", "provider"]
ENTITLEMENT_NS: Final[QuotaPlanNamespace] = "entitlement"
PROVIDER_NS: Final[QuotaPlanNamespace] = "provider"

# ``gateway_quota_plan_usage_buckets`` 命名空间（含 platform 展示读汇总）。
UsageBucketNamespace = Literal["entitlement", "provider", "platform"]
PLATFORM_NS: Final[UsageBucketNamespace] = "platform"

ExhaustedReason = Literal["usd", "tokens", "requests"]

# =============================================================================
# 周期重置策略 - 解决 "本地滚动窗口 vs 厂商日历重置" 的对齐偏差
# =============================================================================
#
# - rolling: 默认；按 ``window_seconds`` 滚动分钟桶（与原行为一致）。
# - calendar_daily_utc: 每日 UTC 00:00 重置（OpenAI/Anthropic/Google 通常如此）。
# - calendar_monthly_utc: 自然月 1 号 UTC 00:00 重置（月套餐）。
ResetStrategy = Literal[
    "rolling",
    "calendar_daily_utc",
    "calendar_monthly_utc",
]
RESET_STRATEGY_DEFAULT: Final[ResetStrategy] = "rolling"

_VALID_RESET_STRATEGIES: Final[frozenset[ResetStrategy]] = frozenset(
    (
        "rolling",
        "calendar_daily_utc",
        "calendar_monthly_utc",
    )
)


def normalize_reset_strategy(value: str) -> ResetStrategy:
    """将仓储/缓存中的字符串归一为合法 ``ResetStrategy``，未知值回退 ``rolling``。"""
    if value in _VALID_RESET_STRATEGIES:
        return cast("ResetStrategy", value)
    return RESET_STRATEGY_DEFAULT


# 与前端「统计窗口」预设一致（quota-window-presets.ts）：日/月窗口默认固定日历重置，
# 仅自定义/子日窗口（无日历对齐语义）回退滚动。作为写入兜底的单一真源。
_DAY_SECONDS: Final = 86400
_MONTH_SECONDS: Final = 2592000


def default_reset_strategy_for_window(window_seconds: int) -> ResetStrategy:
    """未显式指定 ``reset_strategy`` 时按窗口长度推导默认策略。

    - ``86400`` → ``calendar_daily_utc``（每日固定重置）。
    - ``2592000`` → ``calendar_monthly_utc``（每月固定重置）。
    - 其它（含自定义秒数 / ``<=0`` 套餐周期）→ ``rolling``。
    """
    if window_seconds == _DAY_SECONDS:
        return "calendar_daily_utc"
    if window_seconds == _MONTH_SECONDS:
        return "calendar_monthly_utc"
    return RESET_STRATEGY_DEFAULT


def is_sliding_rolling_window(window_seconds: int, reset_strategy: str) -> bool:
    """是否为「真正的滚动窗口」（用量随时间连续滑动、无固定重置时刻）。

    仅当 ``window_seconds > 0`` 且策略为 ``rolling`` 时成立。``window_seconds <= 0``
    表示整套餐有效期累计（总额），即便历史上把 ``reset_strategy`` 默认存成了
    ``rolling``，它也按固定累计处理（窗口起点 = 规则生效时刻），可正常落桶 / 校正。
    展示读跳桶、落库跳桶、用量校正拒绝等"滚动特判"统一以此为单一真源。
    """
    return window_seconds > 0 and normalize_reset_strategy(reset_strategy) == "rolling"


@dataclass(frozen=True)
class PlanQuotaSpec:
    """套餐内单层桶的纯值对象。

    Attributes:
        quota_id: 仓储行主键，用于 Redis key 唯一性。
        label: UI / 错误文案使用的桶名（"5h" / "weekly" / "total"）。
        window_seconds: 窗口长度（秒）；``0`` 表示「整规则有效期作为一个桶」。
        reset_strategy: 见 ``ResetStrategy``；默认 ``rolling``，与历史行为一致。
        limit_*: 任意一项可为 ``None`` 表示该维度不限。任一非空维度耗尽即整桶耗尽。
    """

    quota_id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    reset_strategy: ResetStrategy = RESET_STRATEGY_DEFAULT
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR

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
        - ``window_seconds == 0``：返回 ``None``，由调用方查规则 valid_until。
        """
        when = now or datetime.now(UTC)
        return compute_reset_at(
            strategy=self.spec.reset_strategy,
            window_seconds=self.spec.window_seconds,
            now=when,
            earliest_minute_in_window=self.earliest_minute_in_window,
            period_reset_anchor=self.spec.period_reset_anchor,
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


def _calendar_daily_start(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    if anchor.is_default():
        return _calendar_daily_utc_start(now)
    return compute_period_window_start(now, "daily", anchor)


def _calendar_monthly_start(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    if anchor.is_default():
        return _calendar_monthly_utc_start(now)
    return compute_period_window_start(now, "monthly", anchor)


def _calendar_daily_end(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    if anchor.is_default():
        return _calendar_daily_utc_end(now)
    return _compute_platform_period_reset_at(now, "daily", anchor) or _as_utc(now)


def _calendar_monthly_end(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    if anchor.is_default():
        return _calendar_monthly_utc_end(now)
    return _compute_platform_period_reset_at(now, "monthly", anchor) or _as_utc(now)


def compute_window_start_minute(
    now: datetime,
    window_seconds: int,
    *,
    strategy: ResetStrategy = RESET_STRATEGY_DEFAULT,
    row_valid_from: datetime | None = None,
    period_reset_anchor: PeriodResetAnchor | None = None,
) -> int:
    """根据策略返回当前窗口的"最早有效分钟索引"（含）。

    - ``rolling``：``minute(now) - window_seconds//60``（与历史一致）。
    - ``calendar_daily_utc`` / ``calendar_monthly_utc``：当前自然日/月起点。
    - ``window_seconds == 0``：返回 0（累计计量，调用方按规则 valid_from 处理）。
    """
    if window_seconds <= 0:
        return 0
    anchor = period_reset_anchor or DEFAULT_PERIOD_RESET_ANCHOR
    if strategy == "calendar_daily_utc":
        return compute_minute_index(_calendar_daily_start(now, anchor))
    if strategy == "calendar_monthly_utc":
        return compute_minute_index(_calendar_monthly_start(now, anchor))
    return compute_minute_index(now - timedelta(seconds=window_seconds))


def compute_window_start_datetime(
    now: datetime,
    window_seconds: int,
    *,
    strategy: ResetStrategy = RESET_STRATEGY_DEFAULT,
    row_valid_from: datetime | None = None,
    period_reset_anchor: PeriodResetAnchor | None = None,
) -> datetime:
    """当前配额窗口起点（datetime），与 ``compute_window_start_minute`` 对偶。"""
    if window_seconds <= 0 and row_valid_from is not None:
        return _as_utc(row_valid_from)
    minute_idx = compute_window_start_minute(
        now,
        window_seconds,
        strategy=strategy,
        row_valid_from=row_valid_from,
        period_reset_anchor=period_reset_anchor,
    )
    return datetime.fromtimestamp(minute_idx * 60, tz=UTC)


def compute_reset_at(
    *,
    strategy: ResetStrategy,
    window_seconds: int,
    now: datetime,
    earliest_minute_in_window: int | None = None,
    row_valid_from: datetime | None = None,
    period_reset_anchor: PeriodResetAnchor | None = None,
) -> datetime | None:
    """统一的下次重置时刻计算；与 ``compute_window_start_minute`` 对偶。"""
    _ = row_valid_from
    if window_seconds <= 0:
        return None
    anchor = period_reset_anchor or DEFAULT_PERIOD_RESET_ANCHOR
    if strategy == "calendar_daily_utc":
        return _calendar_daily_end(now, anchor)
    if strategy == "calendar_monthly_utc":
        return _calendar_monthly_end(now, anchor)
    if earliest_minute_in_window is None:
        return now
    earliest_dt = datetime.fromtimestamp(earliest_minute_in_window * 60, tz=UTC)
    return earliest_dt + timedelta(seconds=window_seconds)


__all__ = [
    "DEFAULT_PERIOD_RESET_ANCHOR",
    "ENTITLEMENT_NS",
    "PLATFORM_NS",
    "PROVIDER_NS",
    "RESET_STRATEGY_DEFAULT",
    "ExhaustedReason",
    "PeriodResetAnchor",
    "PlanQuotaSnapshot",
    "PlanQuotaSpec",
    "QuotaPlanCheckResult",
    "QuotaPlanNamespace",
    "QuotaPlanReservation",
    "ResetStrategy",
    "UsageBucketNamespace",
    "compute_minute_index",
    "compute_reset_at",
    "compute_window_start_datetime",
    "compute_window_start_minute",
    "default_reset_strategy_for_window",
    "is_sliding_rolling_window",
    "normalize_reset_strategy",
]
