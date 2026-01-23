"""
Handoff - 任务交接

实现 Agent 之间的任务交接机制
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class HandoffRequest:
    """任务交接请求"""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_agent_id: str = ""
    target_agent_id: str = ""
    task_data: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class HandoffResponse:
    """任务交接响应"""

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    accepted: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class HandoffManager:
    """任务交接管理""

    def __init__(self) -> None:
        self.pending_handoffs: dict[uuid.UUID, HandoffRequest] = {}
        self.completed_handoffs: dict[uuid.UUID, HandoffResponse] = {}

    async def initiate_handoff(
        self,
        source_agent_id: str,
        target_agent_id: str,
        task_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> HandoffRequest:
        """发起任务交接"""
        request = HandoffRequest(
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            task_data=task_data,
            context=context or {},
        )
        self.pending_handoffs[request.id] = request
        return request

    async def complete_handoff(
        self,
        request_id: uuid.UUID,
        accepted: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> HandoffResponse:
        """完成任务交接"""
        response = HandoffResponse(
            request_id=request_id,
            accepted=accepted,
            result=result or {},
            error=error,
        )
        self.completed_handoffs[request_id] = response
        self.pending_handoffs.pop(request_id, None)
        return response
