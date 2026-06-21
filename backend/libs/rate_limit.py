"""
Gateway 按资源速率限制

提供基于 Redis 的固定窗口限流。注意：本项目 ``libs.middleware.rate_limit`` 中的
``RateLimitMiddleware`` 是**内存型、按 user/IP 全局限流**，运行于 ASGI 中间件层，
无法满足"按 ``user_id + model_id`` 维度、跨进程共享计数"的要求，因此探活接口使用
本模块的 Redis 固定窗口实现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status
from fastapi.exceptions import HTTPException

from libs.db.redis import get_redis_client

if TYPE_CHECKING:
    import uuid


PROBE_RATE_LIMIT_PREFIX = "gateway:probe:limit"
PROBE_RATE_LIMIT_WINDOW_SECONDS = 60
PROBE_RATE_LIMIT_MAX_REQUESTS = 1


async def check_fixed_window_rate_limit(
    *,
    key: str,
    window_seconds: int,
    max_requests: int = 1,
) -> None:
    """Redis 固定窗口限流。

    使用 ``SET key 1 NX EX {window}`` 原子操作：仅当 key 不存在时设置成功并放行；
    否则视为窗口内已达上限，返回 429。

    当 ``max_requests > 1`` 时使用 ``INCR`` 计数，仍保持固定窗口语义。
    """
    client = await get_redis_client()

    if max_requests <= 1:
        ok = await client.set(key, "1", nx=True, ex=window_seconds)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(window_seconds)},
            )
        return

    current = await client.incr(key)
    if current == 1:
        await client.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window_seconds)},
        )


async def check_probe_rate_limit(user_id: uuid.UUID, model_id: uuid.UUID) -> None:
    """检查用户对单个模型的探活频率限制（固定窗口，每模型每分钟 1 次）。"""
    key = f"{PROBE_RATE_LIMIT_PREFIX}:{user_id}:{model_id}"
    await check_fixed_window_rate_limit(
        key=key,
        window_seconds=PROBE_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=PROBE_RATE_LIMIT_MAX_REQUESTS,
    )


__all__ = [
    "PROBE_RATE_LIMIT_MAX_REQUESTS",
    "PROBE_RATE_LIMIT_PREFIX",
    "PROBE_RATE_LIMIT_WINDOW_SECONDS",
    "check_fixed_window_rate_limit",
    "check_probe_rate_limit",
]
