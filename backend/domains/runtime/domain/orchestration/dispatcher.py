"""
Dispatcher - 任务分发

负责将任务分发给合适的 Agent?
"""

from typing import Any
import uuid


class TaskDispatcher:
    """任务分发

    根据任务类型Agent 能力，将任务分发给最合适的 Agent?
    """

    def __init__(self) -> None:
        self.agent_capabilities: dict[str, list[str]] = {}
        self.task_queue: list[dict[str, Any]] = []

    def register_agent_capabilities(
        self,
        agent_id: str,
        capabilities: list[str],
    ) -> None:
        """注册 Agent 的能""
        self.agent_capabilities[agent_id] = capabilities

    def find_capable_agent(self, required_capability: str) -> str | None:
        """查找具有指定能力Agent"""
        for agent_id, capabilities in self.agent_capabilities.items():
            if required_capability in capabilities:
                return agent_id
        return None

    async def dispatch(
        self,
        task_type: str,
        task_data: dict[str, Any],
    ) -> dict[str, Any]:
        """分发任务"""
        agent_id = self.find_capable_agent(task_type)
        if not agent_id:
            return {
                "status": "failed",
                "error": f"No agent found with capability: {task_type}",
            }

        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "type": task_type,
            "data": task_data,
            "agent_id": agent_id,
            "status": "dispatched",
        }
        self.task_queue.append(task)

        return {
            "status": "dispatched",
            "task_id": task_id,
            "agent_id": agent_id,
        }
