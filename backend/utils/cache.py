"""
Cache Utilities - 缓存工具

提供 Redis 缓存装饰器和工具函数
"""

from collections.abc import Callable
from contextlib import suppress
from functools import wraps
import hashlib
import json
from typing import Any, ParamSpec, TypeVar

from redis.asyncio import Redis

from bootstrap.config import settings

P = ParamSpec("P")
T = TypeVar("T")

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """获取 Redis 客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """生成缓存键"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()
    return f"{prefix}:{key_hash}"


def cached(ttl: int = 300, key_prefix: str = "cache"):
    """
    缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        key_prefix: 缓存键前缀

    Example:
        @cached(ttl=600, key_prefix="agent")
        async def get_agent(agent_id: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            redis = await get_redis()
            key = cache_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)

            # 尝试从缓存获取
            try:
                cached_value = await redis.get(key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception:
                # 缓存获取失败，继续执行原函数
                pass

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            with suppress(Exception):
                # 缓存写入失败，不影响主流程
                await redis.setex(key, ttl, json.dumps(result, default=str, ensure_ascii=False))

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str) -> int:
    """
    失效匹配模式的缓存

    Args:
        pattern: Redis key 模式（支持 * 通配符）

    Returns:
        失效的缓存数量
    """
    redis = await get_redis()
    count = 0
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)
        count += 1
    return count


async def cache_get(key: str) -> Any | None:
    """获取缓存值"""
    redis = await get_redis()
    value = await redis.get(key)
    if value:
        return json.loads(value)
    return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """设置缓存值"""
    redis = await get_redis()
    await redis.setex(key, ttl, json.dumps(value, default=str, ensure_ascii=False))


async def cache_delete(key: str) -> None:
    """删除缓存"""
    redis = await get_redis()
    await redis.delete(key)
