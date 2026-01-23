"""
A2A 客户端

用于调用其他 Agent
"""

from typing import TYPE_CHECKING, Any

from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.infrastructure.a2a.registry import AgentRegistry

logger = get_logger(__name__)


class A2AClient:
    """
    Agent-to-Agent 客户端

    用于调用其他专业 Agent 执行特定任务
    """

    def __init__(self, registry: "AgentRegistry | None" = None) -> None:
        self.registry = registry

    async def call_agent(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        调用指定的 Agent

        Args:
            agent_id: Agent ID
            task: 任务描述
            context: 上下文信息

        Returns:
            dict: Agent 执行结果
        """
        if not self.registry:
            raise ValueError("Agent registry not configured")

        agent_info = self.registry.get_agent(agent_id)
        if not agent_info:
            raise ValueError(f"Agent {agent_id} not found")

        logger.info("Calling agent %s for task: %s", agent_id, task)

        # TODO: 实现实际的 Agent 调用逻辑
        # 这里应该通过 HTTP/gRPC 等方式调用其他 Agent
        # 或者通过消息队列发送任务

        return {
            "agent_id": agent_id,
            "task": task,
            "result": "Not implemented yet",
            "status": "pending",
        }

    async def call_analyst(
        self,
        data: dict[str, Any],
        analysis_type: str = "general",
    ) -> dict[str, Any]:
        """调用数据分析 Agent"""
        return await self.call_agent(
            "analyst",
            f"Analyze data: {analysis_type}",
            {"data": data},
        )

    async def call_coder(
        self,
        requirement: str,
        language: str = "python",
    ) -> dict[str, Any]:
        """调用代码生成 Agent"""
        return await self.call_agent(
            "coder",
            f"Generate {language} code",
            {"requirement": requirement, "language": language},
        )

    async def call_writer(
        self,
        topic: str,
        style: str = "professional",
    ) -> dict[str, Any]:
        """调用文案写作 Agent"""
        return await self.call_agent(
            "writer",
            f"Write content about {topic}",
            {"topic": topic, "style": style},
        )
