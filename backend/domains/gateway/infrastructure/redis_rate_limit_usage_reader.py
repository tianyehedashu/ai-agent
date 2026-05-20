"""``RateLimitUsageReader`` 的 Redis 实现。

把原本嵌在 ``BudgetService.peek_rate_limit_usage`` 中的 Redis I/O 抽离出来，
让 application 层只依赖 ``domain.proxy_rate_limit_port.RateLimitUsageReader`` 契约。
"""

from __future__ import annotations

from datetime import UTC, datetime

from libs.db.redis import get_redis_client


def _rate_key(scope: str, scope_id: str | None, dimension: str) -> str:
    """与 ``BudgetService`` 内部 ``_rate_key`` 保持完全一致，避免 key 漂移。"""
    sid = scope_id or "system"
    return f"gateway:rate:{scope}:{sid}:{dimension}"


class RedisRateLimitUsageReader:
    """基于 60s Sorted Set 桶的 Redis 实现。"""

    async def peek_60s_window(
        self,
        *,
        scope: str,
        scope_id: str | None,
    ) -> tuple[int, int]:
        client = await get_redis_client()
        now = datetime.now(UTC).timestamp()
        window_start = now - 60
        rpm_key = _rate_key(scope, scope_id, "rpm")
        tpm_key = _rate_key(scope, scope_id, "tpm")
        await client.zremrangebyscore(rpm_key, 0, window_start)
        await client.zremrangebyscore(tpm_key, 0, window_start)
        rpm_used = int(await client.zcard(rpm_key))
        tpm_used = 0
        members = await client.zrange(tpm_key, 0, -1, withscores=True)
        for member, _score in members:
            try:
                payload = member.decode() if isinstance(member, bytes) else str(member)
                parts = payload.split(":", 1)
                if len(parts) == 2:
                    tpm_used += int(parts[0])
            except (ValueError, AttributeError):
                continue
        return rpm_used, tpm_used


__all__ = ["RedisRateLimitUsageReader"]
