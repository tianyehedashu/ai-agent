"""
MCP Server Repository - MCP 服务器仓储

提供 MCP 服务器的数据访问操作
"""

import uuid

from sqlalchemy import Select, and_, func, or_, select

from domains.agent.domain.config.mcp_config import MCPScope, MCPServerEntityConfig
from domains.agent.infrastructure.models.mcp_server import MCPServer
from libs.db.base_repository import OwnedRepositoryBase
from libs.db.permission_context import get_permission_context
from utils.logging import get_logger

logger = get_logger(__name__)


class MCPServerRepository(OwnedRepositoryBase[MCPServer]):
    """MCP 服务器仓储

    继承 OwnedRepositoryBase，自动处理权限过滤
    """

    @property
    def model_class(self) -> type[MCPServer]:
        """返回模型类"""
        return MCPServer

    async def get_by_id(self, server_id: uuid.UUID) -> MCPServer | None:
        """通过 ID 获取服务器（支持系统服务器）"""
        # 对于系统服务器，需要特殊处理
        query = select(self.model_class).where(self.model_class.id == server_id)

        # 不使用 _apply_mcp_scope_filter，而是直接查询
        # 因为系统服务器对所有用户可见（虽然只有管理员能修改）
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _apply_mcp_scope_filter(self, query: Select) -> Select:
        """
        应用 MCP 作用域过滤器

        返回：system 服务器（所有用户可见）+ 当前用户的 user 服务器

        Args:
            query: SQLAlchemy 查询对象

        Returns:
            过滤后的查询
        """
        ctx = get_permission_context()

        # 无权限上下文：只返回 system 服务器
        if not ctx:
            return query.where(self.model_class.scope == "system")

        # 管理员：返回所有服务器
        if ctx.is_admin:
            return query

        # 普通用户：system 服务器 + 自己的 user 服务器
        return query.where(
            or_(
                self.model_class.scope == "system",
                and_(
                    self.model_class.scope == "user",
                    getattr(self.model_class, self.user_id_column) == ctx.user_id,
                ),
            )
        )

    async def list_available(self) -> tuple[list[MCPServer], list[MCPServer]]:
        """
        列出可用的 MCP 服务器

        Returns:
            (system_servers, user_servers) 元组
        """
        # 查询 system 服务器
        system_query = select(self.model_class).where(self.model_class.scope == "system")
        system_query = self._apply_mcp_scope_filter(system_query)
        system_result = await self.db.execute(system_query)
        system_servers = list(system_result.scalars().all())

        # 查询 user 服务器
        user_query = select(self.model_class).where(self.model_class.scope == "user")
        user_query = self._apply_mcp_scope_filter(user_query)
        user_result = await self.db.execute(user_query)
        user_servers = list(user_result.scalars().all())

        return system_servers, user_servers

    async def get_by_name(self, name: str) -> MCPServer | None:
        """根据名称获取服务器"""
        query = select(self.model_class).where(self.model_class.name == name)
        query = self._apply_mcp_scope_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self, config: MCPServerEntityConfig, user_id: uuid.UUID | None = None
    ) -> MCPServer:
        """
        创建 MCP 服务器

        Args:
            config: 服务器配置
            user_id: 创建者 ID（user 级服务器必需）

        Returns:
            创建的 MCP 服务器实例
        """
        if config.scope == MCPScope.USER and not user_id:
            raise ValueError("user_id is required for user-scoped servers")

        server = MCPServer(
            name=config.name,
            display_name=config.display_name,
            url=config.url,
            scope=config.scope.value,
            env_type=config.env_type.value,
            env_config=config.env_config,
            enabled=config.enabled,
            user_id=user_id,
        )
        self.db.add(server)
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def update(
        self,
        server_id: uuid.UUID,
        config: MCPServerEntityConfig,
    ) -> MCPServer | None:
        """
        更新 MCP 服务器

        Args:
            server_id: 服务器 ID
            config: 新配置

        Returns:
            更新后的服务器实例，不存在则返回 None
        """
        server = await self.get_by_id(server_id)
        if not server:
            return None

        # 更新字段
        server.display_name = config.display_name
        server.url = config.url
        server.env_type = config.env_type.value
        server.env_config = config.env_config
        server.enabled = config.enabled

        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def toggle(self, server_id: uuid.UUID, enabled: bool) -> MCPServer | None:
        """
        切换服务器启用状态

        Args:
            server_id: 服务器 ID
            enabled: 启用状态

        Returns:
            更新后的服务器实例，不存在则返回 None
        """
        server = await self.get_by_id(server_id)
        if not server:
            return None

        server.enabled = enabled
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def count_by_scope(self) -> dict[str, int]:
        """
        统计各作用域的服务器数量

        Returns:
            {"system": count, "user": count}
        """
        counts = {}

        # System 服务器
        system_query = select(self.model_class).where(
            self.model_class.scope == "system"
        )
        system_query = self._apply_mcp_scope_filter(system_query)
        system_result = await self.db.execute(
            system_query.with_only_columns(func.count())
        )
        counts["system"] = system_result.scalar() or 0

        # User 服务器
        user_query = select(self.model_class).where(self.model_class.scope == "user")
        user_query = self._apply_mcp_scope_filter(user_query)
        user_result = await self.db.execute(
            user_query.with_only_columns(func.count())
        )
        counts["user"] = user_result.scalar() or 0

        return counts

    async def delete(self, server_id: uuid.UUID) -> bool:
        """
        删除 MCP 服务器

        Args:
            server_id: 服务器 ID

        Returns:
            是否删除成功
        """
        server = await self.get_by_id(server_id)
        if not server:
            return False

        await self.db.delete(server)
        await self.db.flush()  # 立即刷新以便后续查询能看到
        return True
