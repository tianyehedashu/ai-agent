"""
MCP Initialization - MCP 服务器初始化

提供默认系统级 MCP 服务器的自动初始化功能
"""

from sqlalchemy import select

from domains.agent.domain.config.mcp_config import (
    MCPEnvironmentType,
    MCPScope,
    MCPServerEntityConfig,
)
from domains.agent.infrastructure.models.mcp_server import MCPServer
from libs.db.database import get_session_context
from utils.logging import get_logger

logger = get_logger(__name__)


# 默认系统级 MCP 服务器配置（与数据库迁移保持一致）
DEFAULT_SYSTEM_MCPS = [
    MCPServerEntityConfig(
        name="filesystem",
        display_name="文件系统",
        url="stdio://npx -y @modelcontextprotocol/server-filesystem",
        scope=MCPScope.SYSTEM,
        env_type=MCPEnvironmentType.PREINSTALLED,
        env_config={"allowedDirectories": ["."]},
        enabled=True,
    ),
    MCPServerEntityConfig(
        name="github",
        display_name="GitHub",
        url="stdio://npx -y @modelcontextprotocol/server-github",
        scope=MCPScope.SYSTEM,
        env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
        env_config={},
        enabled=False,  # 需要配置 token
    ),
    MCPServerEntityConfig(
        name="postgres",
        display_name="PostgreSQL",
        url="stdio://npx -y @modelcontextprotocol/server-postgres",
        scope=MCPScope.SYSTEM,
        env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
        env_config={"connectionString": ""},
        enabled=False,  # 需要配置连接字符串
    ),
    MCPServerEntityConfig(
        name="slack",
        display_name="Slack",
        url="stdio://npx -y @modelcontextprotocol/server-slack",
        scope=MCPScope.SYSTEM,
        env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
        env_config={},
        enabled=False,  # 需要配置 token
    ),
    MCPServerEntityConfig(
        name="brave-search",
        display_name="Brave 搜索",
        url="stdio://npx -y @modelcontextprotocol/server-brave-search",
        scope=MCPScope.SYSTEM,
        env_type=MCPEnvironmentType.PREINSTALLED,
        env_config={},
        enabled=True,
    ),
]


async def init_default_mcp_servers() -> None:
    """
    初始化默认系统级 MCP 服务器

    检查数据库中是否存在默认的系统级 MCP 服务器，
    如果不存在则自动创建。确保应用启动时有可用的基础 MCP 服务。
    """
    async with get_session_context() as db:
        try:
            # 查询现有的系统级服务器
            result = await db.execute(
                select(MCPServer).where(MCPServer.scope == "system")
            )
            existing_servers = result.scalars().all()
            existing_names = {server.name for server in existing_servers}

            # 创建缺失的默认服务器
            created_count = 0
            for config in DEFAULT_SYSTEM_MCPS:
                if config.name not in existing_names:
                    logger.info("Creating default MCP server: %s", config.name)
                    server = MCPServer(
                        name=config.name,
                        display_name=config.display_name,
                        url=config.url,
                        scope=config.scope.value,
                        env_type=config.env_type.value,
                        env_config=config.env_config,
                        enabled=config.enabled,
                        user_id=None,  # 系统级服务器，user_id 为 NULL
                    )
                    db.add(server)
                    created_count += 1
                else:
                    logger.debug("Default MCP server already exists: %s", config.name)

            if created_count > 0:
                await db.commit()
                logger.info(
                    "Successfully created %d default MCP server(s)", created_count
                )
            else:
                logger.info("All default MCP servers already exist")

        except Exception as e:
            logger.error("Failed to initialize default MCP servers: %s", e, exc_info=True)
            await db.rollback()
