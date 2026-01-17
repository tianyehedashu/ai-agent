"""
MCP 客户端

用于连接和调用 MCP 服务器
"""

import os
from typing import Any

from core.config.execution_config import ExecutionConfig
from utils.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """
    MCP 客户端

    用于连接和调用 MCP 服务器提供的工具
    """

    def __init__(self, server_url: str, api_key: str | None = None) -> None:
        self.server_url = server_url
        self.api_key = api_key
        self._connected = False

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        # TODO: 实现 MCP 协议连接逻辑
        logger.info("Connecting to MCP server: %s", self.server_url)
        self._connected = True

    async def disconnect(self) -> None:
        """断开连接"""
        logger.info("Disconnecting from MCP server")
        self._connected = False

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        列出可用的工具

        Returns:
            list: 工具列表
        """
        if not self._connected:
            await self.connect()

        # TODO: 实现 MCP 协议工具列表获取
        return []

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        调用工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            dict: 工具执行结果
        """
        if not self._connected:
            await self.connect()

        # TODO: 实现 MCP 协议工具调用
        logger.info("Calling MCP tool: %s with args: %s", tool_name, arguments)
        return {
            "tool": tool_name,
            "result": "Not implemented yet",
        }

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            bool: 服务器是否健康
        """
        try:
            # TODO: 实现健康检查
            return self._connected
        except Exception:
            return False


class ConfiguredMCPManager:
    """
    基于 ExecutionConfig 的 MCP 管理器

    根据执行环境配置管理多个 MCP 客户端
    """

    def __init__(self, config: ExecutionConfig) -> None:
        """
        初始化 MCP 管理器

        Args:
            config: 执行环境配置
        """
        self.config = config
        self.clients: dict[str, MCPClient] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化所有启用的 MCP 客户端"""
        if self._initialized:
            return

        for server_name, server_config in self.config.mcp.servers.items():
            if not server_config.enabled:
                logger.debug("MCP server %s is disabled, skipping", server_name)
                continue

            try:
                # 获取 API Key（从环境变量）
                api_key = None
                if server_config.api_key_env:
                    api_key = os.environ.get(server_config.api_key_env)

                # 创建客户端
                client = MCPClient(
                    server_url=server_config.url,
                    api_key=api_key,
                )

                # 如果配置了自动启动，立即连接
                if server_config.auto_start:
                    await client.connect()

                self.clients[server_name] = client
                logger.info(
                    "Initialized MCP client: %s (%s)",
                    server_name,
                    server_config.url,
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize MCP client %s: %s",
                    server_name,
                    e,
                    exc_info=True,
                )

        self._initialized = True

    async def list_all_tools(self) -> list[dict[str, Any]]:
        """
        列出所有 MCP 服务器提供的工具

        Returns:
            工具列表（包含服务器信息）
        """
        await self.initialize()

        all_tools = []
        for server_name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                # 为每个工具添加服务器标识
                for tool in tools:
                    tool["mcp_server"] = server_name
                    all_tools.append(tool)
            except Exception as e:
                logger.error(
                    "Failed to list tools from MCP server %s: %s",
                    server_name,
                    e,
                )

        return all_tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        调用指定服务器的工具

        Args:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        await self.initialize()

        client = self.clients.get(server_name)
        if not client:
            raise ValueError(f"MCP server not found: {server_name}")

        return await client.call_tool(tool_name, arguments)

    async def health_check_all(self) -> dict[str, bool]:
        """
        检查所有 MCP 服务器的健康状态

        Returns:
            服务器名称到健康状态的映射
        """
        await self.initialize()

        results = {}
        for server_name, client in self.clients.items():
            try:
                results[server_name] = await client.health_check()
            except Exception as e:
                logger.error(
                    "Health check failed for MCP server %s: %s",
                    server_name,
                    e,
                )
                results[server_name] = False

        return results

    async def disconnect_all(self) -> None:
        """断开所有 MCP 客户端的连接"""
        for server_name, client in self.clients.items():
            try:
                await client.disconnect()
                logger.info("Disconnected from MCP server: %s", server_name)
            except Exception as e:
                logger.error(
                    "Failed to disconnect from MCP server %s: %s",
                    server_name,
                    e,
                )
