"""
Checkpoint Cache - 检查点缓存

用于短期记忆（Session Memory）的 Redis 缓存实现。
Checkpoint 是短期记忆的存储机制，用于保存会话历史和执行状态。
"""

from typing import Any

from libs.db.redis import CacheService, get_redis


class CheckpointCache(CacheService):
    """检查点缓存

    用于存储 Agent 执行过程中的检查点，支持：
    - 检查点的保存和加载
    - 会话索引管理（按会话 ID 组织检查点）
    - 时间旅行调试（获取历史检查点列表）
    """

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
        """添加到会话索引

        使用 Redis 有序集合（sorted set）维护会话的检查点索引，
        按步骤序号排序，便于快速获取最新或历史检查点。
        """
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
        """获取会话的检查点列表

        返回按步骤序号降序排列的检查点 ID 列表（最新的在前）。
        """
        client = get_redis()
        return await client.zrevrange(
            f"{self.prefix}:index:{session_id}",
            0,
            limit - 1,
        )
