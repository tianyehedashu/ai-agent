"""代理响应限流头（OpenAI / Anthropic 形）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class RateLimitHeaderSnapshot:
    """单次调用后的限流窗口快照（60s 滚动）。"""

    rpm_limit: int | None
    rpm_remaining: int | None
    tpm_limit: int | None
    tpm_remaining: int | None
    reset_epoch: int


def build_rate_limit_snapshot(
    *,
    rpm_limit: int | None,
    rpm_used: int,
    tpm_limit: int | None,
    tpm_used: int,
    window_seconds: int = 60,
) -> RateLimitHeaderSnapshot:
    reset_epoch = int(datetime.now(UTC).timestamp()) + window_seconds
    rpm_remaining = (
        max(0, rpm_limit - rpm_used) if rpm_limit is not None and rpm_limit > 0 else None
    )
    tpm_remaining = (
        max(0, tpm_limit - tpm_used) if tpm_limit is not None and tpm_limit > 0 else None
    )
    return RateLimitHeaderSnapshot(
        rpm_limit=rpm_limit if rpm_limit and rpm_limit > 0 else None,
        rpm_remaining=rpm_remaining,
        tpm_limit=tpm_limit if tpm_limit and tpm_limit > 0 else None,
        tpm_remaining=tpm_remaining,
        reset_epoch=reset_epoch,
    )


def openai_rate_limit_response_headers(
    snap: RateLimitHeaderSnapshot,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if snap.rpm_limit is not None and snap.rpm_remaining is not None:
        headers["x-ratelimit-limit-requests"] = str(snap.rpm_limit)
        headers["x-ratelimit-remaining-requests"] = str(snap.rpm_remaining)
        headers["x-ratelimit-reset-requests"] = str(snap.reset_epoch)
    if snap.tpm_limit is not None and snap.tpm_remaining is not None:
        headers["x-ratelimit-limit-tokens"] = str(snap.tpm_limit)
        headers["x-ratelimit-remaining-tokens"] = str(snap.tpm_remaining)
        headers["x-ratelimit-reset-tokens"] = str(snap.reset_epoch)
    return headers


def anthropic_rate_limit_response_headers(
    snap: RateLimitHeaderSnapshot,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if snap.rpm_limit is not None and snap.rpm_remaining is not None:
        headers["anthropic-ratelimit-requests-limit"] = str(snap.rpm_limit)
        headers["anthropic-ratelimit-requests-remaining"] = str(snap.rpm_remaining)
        headers["anthropic-ratelimit-requests-reset"] = _iso_reset(snap.reset_epoch)
    if snap.tpm_limit is not None and snap.tpm_remaining is not None:
        headers["anthropic-ratelimit-tokens-limit"] = str(snap.tpm_limit)
        headers["anthropic-ratelimit-tokens-remaining"] = str(snap.tpm_remaining)
        headers["anthropic-ratelimit-tokens-reset"] = _iso_reset(snap.reset_epoch)
    return headers


def _iso_reset(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_snapshot_if_no_limits(
    rpm_limit: int | None,
    tpm_limit: int | None,
) -> RateLimitHeaderSnapshot | None:
    if not rpm_limit and not tpm_limit:
        return None
    return build_rate_limit_snapshot(
        rpm_limit=rpm_limit,
        rpm_used=0,
        tpm_limit=tpm_limit,
        tpm_used=0,
    )


__all__ = [
    "RateLimitHeaderSnapshot",
    "anthropic_rate_limit_response_headers",
    "build_rate_limit_snapshot",
    "empty_snapshot_if_no_limits",
    "openai_rate_limit_response_headers",
]
