"""
Checkpointer - 检查点管理器

支持:
- Redis 存储 (快速，用于热数据)
- PostgreSQL 存储 (持久，用于历史)
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from core.types import AgentState, Checkpoint
from db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


class CheckpointStorage(ABC):
    """检查点存储抽象基类"""

    @abstractmethod
    async def save(
        self,
        checkpoint_id: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """保存检查点"""
        ...

    @abstractmethod
    async def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        """加载检查点"""
        ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> None:
        """删除检查点"""
        ...

    @abstractmethod
    async def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[str]:
        """列出会话的检查点"""
        ...


class RedisCheckpointStorage(CheckpointStorage):
    """Redis 检查点存储"""

    def __init__(self, key_prefix: str = "checkpoint:") -> None:
        self.key_prefix = key_prefix
        self.index_prefix = "checkpoint_index:"

    async def save(
        self,
        checkpoint_id: str,
        data: dict[str, Any],
        ttl: int | None = 86400,  # 默认 24 小时
    ) -> None:
        redis = await get_redis_client()
        key = f"{self.key_prefix}{checkpoint_id}"

        # 保存数据
        await redis.set(key, json.dumps(data, default=str))
        if ttl:
            await redis.expire(key, ttl)

        # 添加到会话索引
        session_id = data.get("session_id")
        if session_id:
            index_key = f"{self.index_prefix}{session_id}"
            await redis.zadd(index_key, {checkpoint_id: data.get("step", 0)})
            if ttl:
                await redis.expire(index_key, ttl)

    async def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        redis = await get_redis_client()
        key = f"{self.key_prefix}{checkpoint_id}"

        data = await redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def delete(self, checkpoint_id: str) -> None:
        redis = await get_redis_client()
        key = f"{self.key_prefix}{checkpoint_id}"
        await redis.delete(key)

    async def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[str]:
        redis = await get_redis_client()
        index_key = f"{self.index_prefix}{session_id}"

        # 按 step 倒序获取
        checkpoint_ids = await redis.zrevrange(index_key, 0, limit - 1)
        return [cid.decode() if isinstance(cid, bytes) else cid for cid in checkpoint_ids]


class Checkpointer:
    """
    检查点管理器

    负责检查点的保存、加载和管理
    """

    def __init__(
        self,
        storage: CheckpointStorage | None = None,
        ttl: int = 86400,
    ) -> None:
        self.storage = storage or RedisCheckpointStorage()
        self.ttl = ttl

    async def save(
        self,
        session_id: str,
        step: int,
        state: AgentState,
        parent_id: str | None = None,
    ) -> str:
        """
        保存检查点

        Args:
            session_id: 会话 ID
            step: 步骤号
            state: Agent 状态
            parent_id: 父检查点 ID

        Returns:
            检查点 ID
        """
        checkpoint_id = str(uuid.uuid4())

        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            step=step,
            state=state,
            created_at=datetime.now(timezone.utc),
            parent_id=parent_id,
        )

        await self.storage.save(
            checkpoint_id,
            checkpoint.model_dump(mode="json"),
            self.ttl,
        )

        logger.info(f"Saved checkpoint: {checkpoint_id} (step={step})")
        return checkpoint_id

    async def load(self, checkpoint_id: str) -> AgentState:
        """
        加载检查点状态

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            Agent 状态
        """
        data = await self.storage.load(checkpoint_id)
        if not data:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint = Checkpoint.model_validate(data)
        return checkpoint.state

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        """获取检查点"""
        data = await self.storage.load(checkpoint_id)
        if not data:
            return None
        return Checkpoint.model_validate(data)

    async def get_latest(self, session_id: str) -> Checkpoint | None:
        """获取最新检查点"""
        checkpoint_ids = await self.storage.list_by_session(session_id, limit=1)
        if not checkpoint_ids:
            return None
        return await self.get(checkpoint_ids[0])

    async def list_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Checkpoint]:
        """列出历史检查点"""
        checkpoint_ids = await self.storage.list_by_session(session_id, limit)

        checkpoints = []
        for cid in checkpoint_ids:
            checkpoint = await self.get(cid)
            if checkpoint:
                checkpoints.append(checkpoint)

        return checkpoints

    async def diff(
        self,
        checkpoint_id_1: str,
        checkpoint_id_2: str,
    ) -> dict[str, Any]:
        """对比两个检查点"""
        state1 = await self.load(checkpoint_id_1)
        state2 = await self.load(checkpoint_id_2)

        return {
            "messages_added": len(state2.messages) - len(state1.messages),
            "tokens_delta": state2.total_tokens - state1.total_tokens,
            "iteration_delta": state2.iteration - state1.iteration,
            "status_change": {
                "from": state1.status,
                "to": state2.status,
            },
        }

    async def delete(self, checkpoint_id: str) -> None:
        """删除检查点"""
        await self.storage.delete(checkpoint_id)
