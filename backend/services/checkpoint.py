"""
Checkpoint Service - 检查点服务

实现检查点的存储、加载和管理
"""

import json
import uuid
from datetime import datetime
from typing import Any

from core.types import AgentState, Checkpoint
from db.redis import CheckpointCache


class CheckpointService:
    """检查点服务"""

    def __init__(self) -> None:
        self.cache = CheckpointCache()

    async def save(
        self,
        session_id: str,
        step: int,
        state: AgentState,
        parent_id: str | None = None,
    ) -> str:
        """保存检查点"""
        checkpoint_id = str(uuid.uuid4())

        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            step=step,
            state=state,
            created_at=datetime.utcnow(),
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
        """加载检查点状态"""
        data = await self.cache.get_checkpoint(checkpoint_id)
        if not data:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint = Checkpoint.model_validate(data)
        return checkpoint.state

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        """获取检查点"""
        data = await self.cache.get_checkpoint(checkpoint_id)
        if not data:
            return None
        return Checkpoint.model_validate(data)

    async def get_latest(self, session_id: str) -> Checkpoint | None:
        """获取最新检查点"""
        checkpoint_ids = await self.cache.get_session_checkpoints(session_id, limit=1)
        if not checkpoint_ids:
            return None
        return await self.get(checkpoint_ids[0])

    async def list_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Checkpoint]:
        """列出历史检查点"""
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
        """对比两个检查点的差异"""
        state1 = await self.load(checkpoint_id_1)
        state2 = await self.load(checkpoint_id_2)

        return {
            "messages_added": len(state2.messages) - len(state1.messages),
            "tokens_delta": state2.total_tokens - state1.total_tokens,
            "iteration_delta": state2.iteration - state1.iteration,
            "new_messages": state2.messages[len(state1.messages) :],
        }
