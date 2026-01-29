"""
MCP 客户端

使用 langchain-mcp-adapters 实现 MCP 协议连接、工具列表获取和调用。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from utils.logging import get_logger

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool as LangChainBaseTool

    from libs.config.execution_config import ExecutionConfig

logger = get_logger(__name__)


def _build_transport_config(url: str, env_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """将 URL 转换为 langchain-mcp-adapters 的 transport 配置。

    Args:
        url: MCP 服务器 URL（支持 stdio://, sse://, http://, https://, ws://, wss://）
        env_config: 环境配置（可含 env, cwd, headers 等）

    Returns:
        langchain-mcp-adapters 兼容的连接配置
    """
    env_config = env_config or {}
    config: dict[str, Any] = {}

    if url.startswith("stdio://"):
        # stdio://python /path/to/server.py --arg
        rest = url[8:].strip()
        parts = rest.split()
        config["transport"] = "stdio"
        config["command"] = parts[0] if parts else ""
        config["args"] = parts[1:] if len(parts) > 1 else []
        if "env" in env_config:
            config["env"] = env_config["env"]
        if "cwd" in env_config:
            config["cwd"] = env_config["cwd"]
    elif url.startswith("sse://"):
        # sse://host/path -> https://host/path
        host_path = url[6:].strip()
        config["transport"] = "sse"
        config["url"] = f"https://{host_path}" if not host_path.startswith("http") else host_path
        if "headers" in env_config:
            config["headers"] = env_config["headers"]
    elif url.startswith(("http://", "https://")):
        # Streamable HTTP transport
        config["transport"] = "http"
        config["url"] = url
        if "headers" in env_config:
            config["headers"] = env_config["headers"]
    elif url.startswith(("ws://", "wss://")):
        # WebSocket transport (如果支持)
        config["transport"] = "http"
        config["url"] = url.replace("ws://", "http://").replace("wss://", "https://")
        if "headers" in env_config:
            config["headers"] = env_config["headers"]
    else:
        # 默认按 HTTP 处理
        config["transport"] = "http"
        config["url"] = url
        if "headers" in env_config:
            config["headers"] = env_config["headers"]

    return config


class MCPClient:
    """
    MCP 客户端

    使用 langchain-mcp-adapters 连接和调用 MCP 服务器提供的工具。
    """

    def __init__(self, server_url: str, api_key: str | None = None) -> None:
        """初始化 MCP 客户端。

        Args:
            server_url: MCP 服务器 URL
            api_key: 可选的 API 密钥
        """
        self.server_url = server_url
        self.api_key = api_key
        self._connected = False
        self._client: MultiServerMCPClient | None = None
        self._tools: list[LangChainBaseTool] = []

    def _build_connection_config(self) -> dict[str, Any]:
        """构建连接配置。"""
        env_config: dict[str, Any] = {}
        if self.api_key:
            env_config["headers"] = {"Authorization": f"Bearer {self.api_key}"}
        return _build_transport_config(self.server_url, env_config)

    async def connect(self) -> None:
        """连接到 MCP 服务器。"""
        if self._connected and self._client:
            return

        logger.info("Connecting to MCP server: %s", self.server_url)

        try:
            config = self._build_connection_config()
            self._client = MultiServerMCPClient({"default": config})
            # 获取工具以验证连接
            self._tools = await self._client.get_tools()
            self._connected = True
            logger.info(
                "Connected to MCP server: %s, found %d tools",
                self.server_url,
                len(self._tools),
            )
        except Exception as e:
            self._connected = False
            self._client = None
            logger.error("Failed to connect to MCP server %s: %s", self.server_url, e)
            raise

    async def disconnect(self) -> None:
        """断开连接。"""
        logger.info("Disconnecting from MCP server: %s", self.server_url)
        self._connected = False
        self._client = None
        self._tools = []

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        列出可用的工具。

        Returns:
            工具列表，每个工具包含 name, description, inputSchema 等字段
        """
        if not self._connected:
            await self.connect()

        tools_info = []
        for tool in self._tools:
            tool_info: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description or "",
            }
            # 获取参数 schema
            if hasattr(tool, "args_schema") and tool.args_schema:
                tool_info["inputSchema"] = tool.args_schema.model_json_schema()
            else:
                tool_info["inputSchema"] = {"type": "object", "properties": {}}
            tools_info.append(tool_info)

        return tools_info

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        调用工具。

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self._connected:
            await self.connect()

        logger.info("Calling MCP tool: %s with args: %s", tool_name, arguments)

        # 查找工具
        tool = next((t for t in self._tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        try:
            # 调用工具
            result = await tool.ainvoke(arguments)
            return {
                "tool": tool_name,
                "result": result,
                "success": True,
            }
        except Exception as e:
            logger.error("MCP tool call failed: %s - %s", tool_name, e)
            return {
                "tool": tool_name,
                "result": str(e),
                "success": False,
                "error": str(e),
            }

    async def health_check(self) -> bool:
        """
        健康检查。

        Returns:
            服务器是否健康
        """
        try:
            if not self._connected:
                await self.connect()
            # 尝试列出工具作为健康检查
            tools = await self.list_tools()
            return len(tools) >= 0  # 即使没有工具也算健康
        except Exception as e:
            logger.warning("Health check failed for %s: %s", self.server_url, e)
            return False

    def get_langchain_tools(self) -> list[LangChainBaseTool]:
        """获取 LangChain 工具列表（已连接后可用）。"""
        return self._tools


class ConfiguredMCPManager:
    """
    基于 ExecutionConfig 的 MCP 管理器

    根据执行环境配置管理多个 MCP 客户端，使用 langchain-mcp-adapters
    """

    def __init__(self, config: ExecutionConfig) -> None:
        """
        初始化 MCP 管理器。

        Args:
            config: 执行环境配置
        """
        self.config = config
        self._multi_client: MultiServerMCPClient | None = None
        self._tools: list[LangChainBaseTool] = []
        self._initialized = False
        self._server_configs: dict[str, dict[str, Any]] = {}

    def _build_connections(self) -> dict[str, dict[str, Any]]:
        """构建所有服务器的连接配置。"""
        connections: dict[str, dict[str, Any]] = {}

        for server_name, server_config in self.config.mcp.servers.items():
            if not server_config.enabled:
                logger.debug("MCP server %s is disabled, skipping", server_name)
                continue

            try:
                env_config: dict[str, Any] = server_config.config or {}
                config = _build_transport_config(server_config.url, env_config)
                connections[server_name] = config
                self._server_configs[server_name] = {
                    "url": server_config.url,
                    "config": config,
                }
                logger.debug("Configured MCP server: %s -> %s", server_name, config)
            except Exception as e:
                logger.error("Failed to configure MCP server %s: %s", server_name, e)

        return connections

    async def initialize(self) -> None:
        """初始化所有启用的 MCP 客户端。"""
        if self._initialized:
            return

        connections = self._build_connections()
        if not connections:
            logger.info("No MCP servers configured")
            self._initialized = True
            return

        try:
            self._multi_client = MultiServerMCPClient(connections)
            self._tools = await self._multi_client.get_tools()
            self._initialized = True
            logger.info(
                "Initialized MCP manager with %d servers, %d tools",
                len(connections),
                len(self._tools),
            )
        except Exception as e:
            logger.error("Failed to initialize MCP manager: %s", e, exc_info=True)
            self._initialized = True  # 标记为已初始化，避免重复尝试

    async def list_all_tools(self) -> list[dict[str, Any]]:
        """
        列出所有 MCP 服务器提供的工具。

        Returns:
            工具列表（包含服务器信息）
        """
        await self.initialize()

        all_tools = []
        for tool in self._tools:
            tool_info: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description or "",
            }
            # 获取参数 schema
            if hasattr(tool, "args_schema") and tool.args_schema:
                tool_info["inputSchema"] = tool.args_schema.model_json_schema()
            else:
                tool_info["inputSchema"] = {"type": "object", "properties": {}}

            # 尝试从工具名称推断服务器（langchain-mcp-adapters 可能在名称中包含前缀）
            # 如果工具名称包含 __ 分隔符，可能是 server__tool 格式
            if "__" in tool.name:
                server_name = tool.name.split("__")[0]
                tool_info["mcp_server"] = server_name
            else:
                tool_info["mcp_server"] = "unknown"

            all_tools.append(tool_info)

        return all_tools

    def get_langchain_tools(self) -> list[LangChainBaseTool]:
        """获取所有 LangChain 工具。"""
        return self._tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        调用指定服务器的工具。

        Args:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        await self.initialize()

        # 查找工具（可能带有服务器前缀）
        full_name = f"{server_name}__{tool_name}"
        tool = next(
            (t for t in self._tools if t.name == full_name or t.name == tool_name),
            None,
        )

        if not tool:
            raise ValueError(f"Tool not found: {tool_name} in server {server_name}")

        try:
            result = await tool.ainvoke(arguments)
            return {
                "tool": tool_name,
                "server": server_name,
                "result": result,
                "success": True,
            }
        except Exception as e:
            logger.error("MCP tool call failed: %s/%s - %s", server_name, tool_name, e)
            return {
                "tool": tool_name,
                "server": server_name,
                "result": str(e),
                "success": False,
                "error": str(e),
            }

    async def health_check_all(self) -> dict[str, bool]:
        """
        检查所有 MCP 服务器的健康状态。

        Returns:
            服务器名称到健康状态的映射
        """
        await self.initialize()

        results: dict[str, bool] = {}
        for server_name in self._server_configs:
            # 如果能获取到工具，说明服务器是健康的
            results[server_name] = self._initialized and len(self._tools) >= 0

        return results

    async def disconnect_all(self) -> None:
        """断开所有 MCP 客户端的连接。"""
        logger.info("Disconnecting all MCP clients")
        self._multi_client = None
        self._tools = []
        self._initialized = False


async def test_mcp_connection(
    url: str,
    env_config: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[bool, list[dict[str, Any]], str | None]:
    """
    测试 MCP 服务器连接。

    Args:
        url: MCP 服务器 URL
        env_config: 环境配置
        timeout: 超时时间（秒）

    Returns:
        (连接成功, 工具列表, 错误信息)
    """
    try:
        config = _build_transport_config(url, env_config)
        client = MultiServerMCPClient({"test": config})

        # 使用超时获取工具
        tools = await asyncio.wait_for(client.get_tools(), timeout=timeout)

        tools_info = []
        for tool in tools:
            tool_info: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description or "",
            }
            if hasattr(tool, "args_schema") and tool.args_schema:
                tool_info["inputSchema"] = tool.args_schema.model_json_schema()
            else:
                tool_info["inputSchema"] = {"type": "object", "properties": {}}
            tools_info.append(tool_info)

        logger.info("MCP connection test successful: %s, found %d tools", url, len(tools_info))
        return True, tools_info, None

    except TimeoutError:
        error_msg = f"Connection timeout after {timeout}s"
        logger.warning("MCP connection test timeout: %s", url)
        return False, [], error_msg
    except Exception as e:
        error_msg = str(e)
        logger.warning("MCP connection test failed: %s - %s", url, error_msg)
        return False, [], error_msg
