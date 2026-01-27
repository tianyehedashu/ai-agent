"""
MCP 工具服务

从数据库加载 MCP 服务器配置并初始化工具
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from libs.config.execution_config import (
    ExecutionConfig,
    MCPConfig,
    MCPServerConfig,
)

from domains.agent.domain.config.mcp_config import MCPScope, MCPServerEntityConfig
from domains.agent.infrastructure.repositories.mcp_server_repository import (
    MCPServerRepository,
)
from domains.agent.infrastructure.tools.base import BaseTool
from domains.agent.infrastructure.tools.mcp.client import ConfiguredMCPManager
from domains.agent.infrastructure.tools.mcp.wrapper import MCPToolWrapper
from utils.logging import get_logger

logger = get_logger(__name__)


class MCPToolService:
    """
    MCP 工具服务

    负责从数据库加载 MCP 服务器配置，初始化 MCP 客户端，
    并将 MCP 工具包装为 BaseTool
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = MCPServerRepository(db)
        self._mcp_manager: ConfiguredMCPManager | None = None
        self._enabled_servers: list[MCPServerEntityConfig] = []

    async def load_enabled_servers(
        self, enabled_server_ids: list[uuid.UUID]
    ) -> list[MCPServerEntityConfig]:
        """
        加载启用的 MCP 服务器配置

        Args:
            enabled_server_ids: 启用的服务器 ID 列表

        Returns:
            启用的服务器配置列表
        """
        if not enabled_server_ids:
            logger.debug("No enabled MCP servers for this session")
            return []

        # 从数据库加载服务器配置
        servers = []
        for server_id in enabled_server_ids:
            try:
                server = await self.repository.get_by_id(server_id)
                if server and server.enabled:
                    # 转换为 Domain Config
                    server_config = MCPServerEntityConfig(
                        id=server.id,
                        name=server.name,
                        display_name=server.display_name,
                        url=server.url,
                        scope=MCPScope(server.scope),
                        user_id=server.user_id,
                        env_type=server.env_type,
                        env_config=server.env_config,
                        enabled=server.enabled,
                    )
                    servers.append(server_config)
                    logger.debug(
                        "Loaded MCP server: %s (%s)", server.name, server.scope
                    )
                else:
                    logger.warning("MCP server %s is disabled or not found", server_id)
            except Exception as e:
                logger.error(
                    "Failed to load MCP server %s: %s", server_id, e, exc_info=True
                )

        self._enabled_servers = servers
        return servers

    async def initialize_mcp_manager(self) -> ConfiguredMCPManager | None:
        """
        初始化 ConfiguredMCPManager

        将数据库中的 MCP 服务器配置转换为 ExecutionConfig 兼容的格式
        """
        if not self._enabled_servers:
            logger.debug("No MCP servers to initialize")
            return None

        # 构造临时的 ExecutionConfig（仅用于 MCP 配置）
        mcp_servers = {}
        for server_config in self._enabled_servers:
            # 转换为 MCPServerConfig
            mcp_server_config = MCPServerConfig(
                name=server_config.name,
                description=server_config.display_name or server_config.name,
                url=server_config.url,
                enabled=server_config.enabled,
                auto_start=True,  # 会话启动时自动连接
                config=server_config.env_config,
            )
            mcp_servers[server_config.name] = mcp_server_config

        # 创建 MCPConfig
        mcp_config = MCPConfig(servers=mcp_servers)

        # 创建临时 ExecutionConfig
        execution_config = ExecutionConfig(mcp=mcp_config)

        # 初始化 ConfiguredMCPManager
        try:
            mcp_manager = ConfiguredMCPManager(config=execution_config)
            await mcp_manager.initialize()
            self._mcp_manager = mcp_manager
            logger.info(
                "Initialized MCP manager with %d servers",
                len(self._enabled_servers),
            )
            return mcp_manager
        except Exception as e:
            logger.error(
                "Failed to initialize MCP manager: %s",
                e,
                exc_info=True,
            )
            return None

    async def get_mcp_tools(self) -> list[BaseTool]:
        """
        获取所有 MCP 工具（包装为 BaseTool）

        Returns:
            BaseTool 列表
        """
        if not self._mcp_manager:
            return []

        try:
            # 列出所有工具
            all_tools_definitions = await self._mcp_manager.list_all_tools()

            # 包装为 BaseTool
            tools = []
            for tool_def in all_tools_definitions:
                server_name = tool_def.get("mcp_server", "unknown")
                tool_name = tool_def.get("name", "unknown")

                # 创建包装器
                wrapper = MCPToolWrapper(
                    mcp_client=self._mcp_manager,
                    server_name=server_name,
                    tool_name=tool_name,
                    tool_definition=tool_def,
                )
                tools.append(wrapper)
                logger.debug(
                    "Wrapped MCP tool: %s__%s", server_name, tool_name
                )

            logger.info("Loaded %d MCP tools", len(tools))
            return tools
        except Exception as e:
            logger.error(
                "Failed to get MCP tools: %s",
                e,
                exc_info=True,
            )
            return []

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mcp_manager:
            try:
                await self._mcp_manager.disconnect_all()
                logger.info("Disconnected all MCP clients")
            except Exception as e:
                logger.error("Failed to disconnect MCP clients: %s", e)
