"""
Redis Connection Management
"""

import contextlib
import json
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import redis.asyncio as redis

from bootstrap.config import settings


def build_authenticated_redis_url(base_url: str) -> str:
    """把 ``settings`` 中的 ACL ``username``/``password`` 注入 redis URL。

    供仅接受 ``redis_url`` 字符串、不支持单独 username 参数的客户端使用
    （如 LiteLLM Router —— 其 redis_url 最终交给 ``redis.Redis.from_url`` 解析）。
    阿里云 Redis 启用 ACL 后必须 ``AUTH <username> <password>``，仅传密码会
    被拒为 ``WRONGPASS``。URL 已自带凭据或未配置凭据时原样返回。
    """
    if not (settings.redis_username or settings.redis_password):
        return base_url
    parts = urlsplit(base_url)
    if parts.username or parts.password:
        return base_url
    user = quote(settings.redis_username or "", safe="")
    pwd = quote(settings.redis_password or "", safe="")
    host = parts.hostname or ""
    netloc = f"{user}:{pwd}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

# 全局 Redis 客户端（decode_responses=True 时 value 为 str）
# 注：redis.asyncio.client.Redis 在部分版本不支持泛型，使用 Any
_redis_client: Any | None = None
_redis_loop_id: int | None = None


def _redis_connect_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {
        "encoding": "utf-8",
        "decode_responses": True,
    }
    if settings.redis_username:
        kwargs["username"] = settings.redis_username
    if settings.redis_password:
        kwargs["password"] = settings.redis_password
    return kwargs


async def init_redis() -> None:
    """初始化 Redis 连接"""
    global _redis_client

    _redis_client = redis.from_url(
        settings.redis_url,
        **_redis_connect_kwargs(),
    )

    # 测试连接
    await _redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_client, _redis_loop_id

    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        _redis_loop_id = None


def get_redis() -> Any:
    """获取 Redis 客户端 (同步方式)"""
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def _reset_redis_client_if_loop_changed() -> None:
    """pytest-asyncio 每用例换 event loop 时，丢弃旧 loop 绑定的连接。"""
    global _redis_client, _redis_loop_id

    if _redis_client is None:
        return
    import asyncio

    loop_id = id(asyncio.get_running_loop())
    if _redis_loop_id == loop_id:
        return
    with contextlib.suppress(Exception):
        await _redis_client.aclose()
    _redis_client = None
    _redis_loop_id = None


async def get_redis_client() -> Any:
    """获取 Redis 客户端 (异步方式，自动初始化)"""
    global _redis_client, _redis_loop_id

    await _reset_redis_client_if_loop_changed()
    if _redis_client is None:
        import asyncio

        _redis_client = redis.from_url(
            settings.redis_url,
            **_redis_connect_kwargs(),
        )
        _redis_loop_id = id(asyncio.get_running_loop())

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
