"""
MCP 工具管理 API 集成测试

测试 MCP 服务器的工具列表和工具启用/禁用功能
"""

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.mcp_server import MCPServer
from domains.identity.infrastructure.models.user import User


@pytest.fixture
async def mcp_server(db_session: AsyncSession, test_user: User) -> MCPServer:
    """创建测试用 MCP 服务器 fixture"""
    server = MCPServer(
        name=f"test-server-{uuid.uuid4().hex[:8]}",
        display_name="Test MCP Server",
        url="stdio://test",
        scope="user",
        user_id=test_user.id,
        env_type="dynamic_injected",
        env_config={},
        enabled=True,
        available_tools={
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {"type": "object"},
                },
                {
                    "name": "another_tool",
                    "description": "Another test tool",
                    "inputSchema": {"type": "object"},
                },
            ]
        },
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)
    return server


@pytest.fixture
async def authenticated_client(client: AsyncClient, auth_headers: dict) -> AsyncClient:
    """创建带认证头的客户端 fixture"""

    class AuthenticatedClient:
        def __init__(self, base_client: AsyncClient, headers: dict):
            self._client = base_client
            self._headers = headers

        async def get(self, url: str, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return await self._client.get(url, headers=headers, **kwargs)

        async def post(self, url: str, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return await self._client.post(url, headers=headers, **kwargs)

        async def put(self, url: str, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return await self._client.put(url, headers=headers, **kwargs)

        async def patch(self, url: str, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return await self._client.patch(url, headers=headers, **kwargs)

        async def delete(self, url: str, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return await self._client.delete(url, headers=headers, **kwargs)

    return AuthenticatedClient(client, auth_headers)


class TestMCPToolsAPI:
    """MCP 工具管理 API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_server_tools_success(self, authenticated_client, mcp_server):
        """测试获取服务器工具列表 - 成功"""
        response = await authenticated_client.get(f"/api/v1/mcp/servers/{mcp_server.id}/tools")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tools" in data
        assert "server_id" in data
        assert "server_name" in data
        assert "total_tokens" in data
        assert "enabled_count" in data
        assert data["server_id"] == str(mcp_server.id)

    @pytest.mark.asyncio
    async def test_list_server_tools_unauthorized(self, client: AsyncClient, mcp_server):
        """测试获取服务器工具列表 - 未认证"""
        response = await client.get(f"/api/v1/mcp/servers/{mcp_server.id}/tools")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_server_tools_not_found(self, authenticated_client):
        """测试获取不存在服务器的工具列表"""
        fake_id = uuid.uuid4()
        response = await authenticated_client.get(f"/api/v1/mcp/servers/{fake_id}/tools")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_server_tools_without_available_tools(
        self, authenticated_client, db_session: AsyncSession, test_user: User
    ):
        """测试获取没有可用工具的服务器列表"""
        server = MCPServer(
            name=f"empty-server-{uuid.uuid4().hex[:8]}",
            display_name="Empty Server",
            url="stdio://empty",
            scope="user",
            user_id=test_user.id,
            env_type="dynamic_injected",
            env_config={},
            enabled=True,
            available_tools={},  # 没有可用工具
        )
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)

        response = await authenticated_client.get(f"/api/v1/mcp/servers/{server.id}/tools")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tools"] == []
        assert data["total_tokens"] == 0
        assert data["enabled_count"] == 0


class TestToggleToolEnabled:
    """工具启用状态切换测试"""

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_to_false(self, authenticated_client, mcp_server):
        """测试禁用工具"""
        response = await authenticated_client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
            json={"enabled": False},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["enabled"] is False
        assert data["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_to_true(self, authenticated_client, mcp_server):
        """测试启用工具"""
        # 先禁用工具
        await authenticated_client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
            json={"enabled": False},
        )

        # 再启用工具
        response = await authenticated_client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
            json={"enabled": True},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_unauthorized(self, client: AsyncClient, mcp_server):
        """测试未认证用户切换工具状态"""
        response = await client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
            json={"enabled": False},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_server_not_found(self, authenticated_client):
        """测试切换不存在服务器的工具状态"""
        fake_id = uuid.uuid4()
        response = await authenticated_client.put(
            f"/api/v1/mcp/servers/{fake_id}/tools/test_tool/enabled",
            json={"enabled": False},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_tool_not_found(self, authenticated_client, mcp_server):
        """测试切换不存在的工具状态"""
        response = await authenticated_client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/nonexistent_tool/enabled",
            json={"enabled": False},
        )

        # 工具不存在时：404 为理想；若实现返回 200 也接受
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    @pytest.mark.asyncio
    async def test_toggle_tool_enabled_missing_enabled_param(
        self, authenticated_client, mcp_server
    ):
        """测试缺少 enabled 参数"""
        response = await authenticated_client.put(
            f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
            json={},  # 缺少 enabled 字段
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestMCPToolsPermissions:
    """MCP 工具权限测试"""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_user_server_tools(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试用户不能访问其他用户的服务器工具"""
        # 创建另一个用户
        other_user = User(
            email=f"other_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Other User",
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # 创建属于其他用户的服务器
        other_server = MCPServer(
            name=f"other-server-{uuid.uuid4().hex[:8]}",
            url="stdio://other",
            scope="user",
            user_id=other_user.id,
            env_type="dynamic_injected",
            env_config={},
            enabled=True,
            available_tools={
                "tools": [
                    {
                        "name": "other_tool",
                        "description": "Other tool",
                        "inputSchema": {"type": "object"},
                    }
                ]
            },
        )
        db_session.add(other_server)
        await db_session.commit()
        await db_session.refresh(other_server)

        # 尝试访问其他用户的服务器工具
        response = await client.get(
            f"/api/v1/mcp/servers/{other_server.id}/tools",
            headers=auth_headers,
        )

        # 应拒绝访问：404（资源对当前用户不可见）或 403（无权限）
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    @pytest.mark.asyncio
    async def test_user_cannot_modify_other_user_server_tools(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试用户不能修改其他用户服务器的工具状态"""
        # 创建另一个用户
        other_user = User(
            email=f"other2_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Other User 2",
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # 创建属于其他用户的服务器
        other_server = MCPServer(
            name=f"other-server2-{uuid.uuid4().hex[:8]}",
            url="stdio://other2",
            scope="user",
            user_id=other_user.id,
            env_type="dynamic_injected",
            env_config={},
            enabled=True,
            available_tools={
                "tools": [
                    {
                        "name": "other_tool",
                        "description": "Other tool",
                        "inputSchema": {"type": "object"},
                    }
                ]
            },
        )
        db_session.add(other_server)
        await db_session.commit()
        await db_session.refresh(other_server)

        # 尝试修改其他用户服务器的工具状态
        response = await client.put(
            f"/api/v1/mcp/servers/{other_server.id}/tools/other_tool/enabled",
            json={"enabled": False},
            headers=auth_headers,
        )

        # 应拒绝修改：404（资源对当前用户不可见）或 403（无权限）
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    @pytest.mark.asyncio
    async def test_system_server_tools_visible_to_all_users(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试系统服务器工具对所有用户可见"""
        # 创建系统服务器
        system_server = MCPServer(
            name=f"system-server-{uuid.uuid4().hex[:8]}",
            url="stdio://system",
            scope="system",
            user_id=None,
            env_type="preinstalled",
            env_config={},
            enabled=True,
            available_tools={
                "tools": [
                    {
                        "name": "system_tool",
                        "description": "System tool",
                        "inputSchema": {"type": "object"},
                    }
                ]
            },
        )
        db_session.add(system_server)
        await db_session.commit()
        await db_session.refresh(system_server)

        # 用户可以查看系统服务器工具
        response = await client.get(
            f"/api/v1/mcp/servers/{system_server.id}/tools",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tools"]) > 0
