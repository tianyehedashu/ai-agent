"""
Redis Connection Management
"""

import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

# 全局 Redis 客户端
_redis_client: redis.Redis | None = None


async def init_redis() -> None:
    """初始化 Redis 连接"""
    global _redis_client

    _redis_client = redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        encoding="utf-8",
        decode_responses=True,
    )

    # 测试连接
    await _redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端 (同步方式)"""
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端 (异步方式，自动初始化)"""
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            encoding="utf-8",
            decode_responses=True,
        )

    return _redis_client


class CacheService:
    """缓存服务"""

    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """生成缓存键"""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """获取缓存"""
        client = get_redis()
        value = await client.get(self._key(key))
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """设置缓存"""
        client = get_redis()
        json_value = json.dumps(value, ensure_ascii=False, default=str)
        if ttl:
            await client.setex(self._key(key), ttl, json_value)
        else:
            await client.set(self._key(key), json_value)

    async def delete(self, key: str) -> None:
        """删除缓存"""
        client = get_redis()
        await client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        client = get_redis()
        return bool(await client.exists(self._key(key)))

    async def expire(self, key: str, ttl: int) -> None:
        """设置过期时间"""
        client = get_redis()
        await client.expire(self._key(key), ttl)

    async def incr(self, key: str, amount: int = 1) -> int:
        """递增"""
        client = get_redis()
        return await client.incrby(self._key(key), amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """递减"""
        client = get_redis()
        return await client.decrby(self._key(key), amount)


class SessionCache(CacheService):
    """会话缓存"""

    def __init__(self) -> None:
        super().__init__(prefix="session")


class CheckpointCache(CacheService):
    """检查点缓存"""

    def __init__(self) -> None:
        super().__init__(prefix="checkpoint")

    async def save_checkpoint(
        self,
        checkpoint_id: str,
        data: dict[str, Any],
        ttl: int = 86400 * 7,  # 7 天
    ) -> None:
        """保存检查点"""
        await self.set(checkpoint_id, data, ttl=ttl)

    async def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """获取检查点"""
        return await self.get(checkpoint_id)

    async def add_to_session_index(
        self,
        session_id: str,
        checkpoint_id: str,
        step: int,
    ) -> None:
        """添加到会话索引"""
        client = get_redis()
        await client.zadd(
            f"{self.prefix}:index:{session_id}",
            {checkpoint_id: step},
        )

    async def get_session_checkpoints(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[str]:
        """获取会话的检查点列表"""
        client = get_redis()
        return await client.zrevrange(
            f"{self.prefix}:index:{session_id}",
            0,
            limit - 1,
        )
