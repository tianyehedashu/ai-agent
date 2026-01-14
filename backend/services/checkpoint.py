"""
Checkpoint Service - 检查点服务

实现检查点的存储、加载和管理。
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.types import AgentState, Checkpoint
from db.redis import CheckpointCache
from exceptions import CheckpointError


class CheckpointService:
    """检查点服务

    管理 Agent 执行过程中的检查点，支持时间旅行调试。

    Attributes:
        db: 数据库会话
        cache: Redis 缓存
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cache = CheckpointCache()

    async def save(
        self,
        session_id: str,
        step: int,
        state: AgentState,
        parent_id: str | None = None,
    ) -> str:
        """保存检查点

        Args:
            session_id: 会话 ID
            step: 执行步骤
            state: Agent 状态
            parent_id: 父检查点 ID（可选）

        Returns:
            检查点 ID
        """
        checkpoint_id = str(uuid.uuid4())

        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            step=step,
            state=state,
            created_at=datetime.now(UTC),
            parent_id=parent_id,
        )

        # 保存到缓存
        await self.cache.save_checkpoint(
            checkpoint_id,
            checkpoint.model_dump(mode="json"),
        )

        # 添加到会话索引
        await self.cache.add_to_session_index(session_id, checkpoint_id, step)

        return checkpoint_id

    async def load(self, checkpoint_id: str) -> AgentState:
        """加载检查点状态

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            Agent 状态

        Raises:
            CheckpointError: 检查点不存在时
        """
        data = await self.cache.get_checkpoint(checkpoint_id)
        if not data:
            raise CheckpointError(
                f"Checkpoint not found: {checkpoint_id}",
                checkpoint_id=checkpoint_id,
            )

        checkpoint = Checkpoint.model_validate(data)
        return checkpoint.state

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        """获取检查点

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            检查点对象或 None
        """
        data = await self.cache.get_checkpoint(checkpoint_id)
        if not data:
            return None
        return Checkpoint.model_validate(data)

    async def get_or_raise(self, checkpoint_id: str) -> Checkpoint:
        """获取检查点，不存在则抛出异常

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            检查点对象

        Raises:
            CheckpointError: 检查点不存在时
        """
        checkpoint = await self.get(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(
                f"Checkpoint not found: {checkpoint_id}",
                checkpoint_id=checkpoint_id,
            )
        return checkpoint

    async def get_latest(self, session_id: str) -> Checkpoint | None:
        """获取会话的最新检查点

        Args:
            session_id: 会话 ID

        Returns:
            最新检查点或 None
        """
        checkpoint_ids = await self.cache.get_session_checkpoints(session_id, limit=1)
        if not checkpoint_ids:
            return None
        return await self.get(checkpoint_ids[0])

    async def list_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Checkpoint]:
        """列出会话的历史检查点

        Args:
            session_id: 会话 ID
            limit: 返回数量限制

        Returns:
            检查点列表
        """
        checkpoint_ids = await self.cache.get_session_checkpoints(session_id, limit=limit)

        checkpoints = []
        for checkpoint_id in checkpoint_ids:
            checkpoint = await self.get(checkpoint_id)
            if checkpoint:
                checkpoints.append(checkpoint)

        return checkpoints

    async def diff(
        self,
        checkpoint_id_1: str,
        checkpoint_id_2: str,
    ) -> dict[str, Any]:
        """对比两个检查点的差异

        Args:
            checkpoint_id_1: 第一个检查点 ID
            checkpoint_id_2: 第二个检查点 ID

        Returns:
            差异信息字典

        Raises:
            CheckpointError: 检查点不存在时
        """
        state1 = await self.load(checkpoint_id_1)
        state2 = await self.load(checkpoint_id_2)

        return {
            "messages_added": len(state2.messages) - len(state1.messages),
            "tokens_delta": state2.total_tokens - state1.total_tokens,
            "iteration_delta": state2.iteration - state1.iteration,
            "new_messages": state2.messages[len(state1.messages) :],
        }
