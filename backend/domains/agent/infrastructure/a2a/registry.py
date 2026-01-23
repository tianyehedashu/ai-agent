"""
Agent 注册表

管理可用的 Agent 信息
"""

from utils.logging import get_logger

logger = get_logger(__name__)


class AgentInfo:
    """Agent 信息"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        endpoint: str | None = None,
        capabilities: list[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.endpoint = endpoint
        self.capabilities = capabilities or []


class AgentRegistry:
    """
    Agent 注册表

    管理系统中所有可用的 Agent
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._load_default_agents()

    def _load_default_agents(self) -> None:
        """加载默认 Agent"""
        default_agents = [
            AgentInfo(
                agent_id="analyst",
                name="数据分析 Agent",
                description="专门用于数据分析和统计",
                capabilities=["data_analysis", "statistics", "visualization"],
            ),
            AgentInfo(
                agent_id="coder",
                name="代码生成 Agent",
                description="专门用于代码生成和编程任务",
                capabilities=["code_generation", "code_review", "debugging"],
            ),
            AgentInfo(
                agent_id="writer",
                name="文案写作 Agent",
                description="专门用于内容创作和文案写作",
                capabilities=["content_creation", "copywriting", "editing"],
            ),
        ]

        for agent in default_agents:
            self.register(agent)

    def register(self, agent: AgentInfo) -> None:
        """
        注册 Agent

        Args:
            agent: Agent 信息
        """
        self._agents[agent.agent_id] = agent
        logger.info("Registered agent: %s (%s)", agent.agent_id, agent.name)

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """
        获取 Agent 信息

        Args:
            agent_id: Agent ID

        Returns:
            AgentInfo | None: Agent 信息
        """
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentInfo]:
        """
        列出所有 Agent

        Returns:
            list[AgentInfo]: Agent 列表
        """
        return list(self._agents.values())

    def list_by_capability(self, capability: str) -> list[AgentInfo]:
        """
        根据能力列出 Agent

        Args:
            capability: 能力名称

        Returns:
            list[AgentInfo]: 符合条件的 Agent 列表
        """
        return [agent for agent in self._agents.values() if capability in agent.capabilities]
