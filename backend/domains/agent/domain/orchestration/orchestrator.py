"""
Orchestrator - 编排

负责协调多个 Agent 之间的交互和任务分配
"""

from typing import Any


class Orchestrator:
    """编排

    协调多个 Agent 之间的交互，支持任务分配和结果聚合
    """

    def __init__(self) -> None:
        self.agents: dict[str, Any] = {}
        self.tasks: dict[str, Any] = {}

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """注册 Agent"""
        self.agents[agent_id] = agent

    def unregister_agent(self, agent_id: str) -> None:
        """注销 Agent"""
        self.agents.pop(agent_id, None)

    async def dispatch_task(
        self,
        task_id: str,
        agent_id: str,
        task_data: dict[str, Any],
    ) -> dict[str, Any]:
        """分派任务给指Agent"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        # TODO: 实现实际的任务分派逻辑
        # agent = self.agents[agent_id]  # 将在实现时使
        return {"task_id": task_id, "status": "dispatched"}

    async def aggregate_results(
        self,
        task_ids: list[str],
    ) -> dict[str, Any]:
        """聚合多个任务的结果"""
        results = {}
        for task_id in task_ids:
            if task_id in self.tasks:
                results[task_id] = self.tasks[task_id]
        return results
