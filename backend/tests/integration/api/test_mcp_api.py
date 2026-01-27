"""
MCP API 集成测试

测试 MCP 管理 API 端点的完整功能
"""

from fastapi import status
from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.mcp_server import MCPServer
from domains.identity.infrastructure.models.user import User


@pytest.fixture(autouse=True)
async def setup_system_mcp_servers(db_session: AsyncSession):
    """为测试创建默认系统级 MCP 服务器"""
    # 检查是否已存在系统服务器
    result = await db_session.execute(
        select(MCPServer).where(MCPServer.scope == "system")
    )
    existing = result.scalars().all()

    if not existing:
        # 创建默认系统服务器（与迁移中的数据一致）
        system_servers = [
            MCPServer(
                name="filesystem",
                display_name="文件系统",
                url="stdio://npx -y @modelcontextprotocol/server-filesystem",
                scope="system",
                env_type="preinstalled",
                env_config={"allowedDirectories": ["."]},
                enabled=True,
                description="访问本地文件系统",
                category="productivity",
            ),
            MCPServer(
                name="github",
                display_name="GitHub",
                url="stdio://npx -y @modelcontextprotocol/server-github",
                scope="system",
                env_type="dynamic_injected",
                env_config={},
                enabled=False,
                description="GitHub 仓库集成（需要配置 token）",
                category="development",
            ),
            MCPServer(
                name="postgres",
                display_name="PostgreSQL",
                url="stdio://npx -y @modelcontextprotocol/server-postgres",
                scope="system",
                env_type="dynamic_injected",
                env_config={"connectionString": ""},
                enabled=False,
                description="PostgreSQL 数据库访问",
                category="database",
            ),
            MCPServer(
                name="slack",
                display_name="Slack",
                url="stdio://npx -y @modelcontextprotocol/server-slack",
                scope="system",
                env_type="dynamic_injected",
                env_config={},
                enabled=False,
                description="Slack 集成（需要配置 token）",
                category="communication",
            ),
            MCPServer(
                name="brave-search",
                display_name="Brave 搜索",
                url="stdio://npx -y @modelcontextprotocol/server-brave-search",
                scope="system",
                env_type="preinstalled",
                env_config={},
                enabled=True,
                description="Brave 网页搜索",
                category="search",
            ),
        ]

        for server in system_servers:
            db_session.add(server)

        await db_session.commit()

    yield

    # 测试后不需要清理，因为每个测试都会回滚


class TestMCPTemplatesAPI:
    """MCP 模板 API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_templates_requires_auth(self, client: AsyncClient):
        """测试: 列出模板需要认证"""
        # Act
        response = await client.get("/api/v1/mcp/templates", follow_redirects=False)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_templates(self, client: AsyncClient, auth_headers: dict):
        """测试: 列出所有模板"""
        # Act
        response = await client.get(
            "/api/v1/mcp/templates",
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # 至少有 5 个内置模板

        # 验证模板结构
        template = data[0]
        assert "id" in template
        assert "name" in template
        assert "display_name" in template
        assert "category" in template


class TestMCPServersAPI:
    """MCP 服务器 API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_servers_requires_auth(self, client: AsyncClient):
        """测试: 列出服务器需要认证"""
        # Act
        response = await client.get("/api/v1/mcp/servers", follow_redirects=False)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_servers(self, client: AsyncClient, auth_headers: dict):
        """测试: 列出服务器"""
        # Act
        response = await client.get(
            "/api/v1/mcp/servers",
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "system_servers" in data
        assert "user_servers" in data
        assert isinstance(data["system_servers"], list)
        assert isinstance(data["user_servers"], list)

    @pytest.mark.asyncio
    async def test_create_server(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """测试: 创建 MCP 服务器"""
        # Arrange
        server_data = {
            "name": "test-github",
            "display_name": "Test GitHub",
            "url": "stdio://github",
            "env_type": "dynamic_injected",
            "env_config": {"github_token": "test_token"},
            "enabled": True,
        }

        # Act
        response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "test-github"
        assert data["display_name"] == "Test GitHub"
        assert data["scope"] == "user"
        assert "id" in data

        # 清理：删除测试创建的服务器
        server_id = data["id"]
        await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_server_duplicate_name_fails(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """测试: 创建重名服务器应该失败"""
        # Arrange - 创建第一个服务器
        server_data = {
            "name": "duplicate-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        response1 = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Act - 尝试创建重名服务器
        response2 = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )

        # Assert
        assert response2.status_code == status.HTTP_409_CONFLICT

        # 清理
        server_id = response1.json()["id"]
        await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_toggle_server(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 切换服务器启用状态"""
        # Arrange - 创建服务器
        server_data = {
            "name": "toggle-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
            "enabled": True,
        }

        create_response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        server_id = create_response.json()["id"]
        assert create_response.json()["enabled"] is True

        # Act - 禁用服务器
        disable_response = await client.patch(
            f"/api/v1/mcp/servers/{server_id}/toggle?enabled=false",
            headers=auth_headers,
        )

        # Assert
        assert disable_response.status_code == status.HTTP_200_OK
        assert disable_response.json()["enabled"] is False

        # Act - 启用服务器
        enable_response = await client.patch(
            f"/api/v1/mcp/servers/{server_id}/toggle?enabled=true",
            headers=auth_headers,
        )

        # Assert
        assert enable_response.status_code == status.HTTP_200_OK
        assert enable_response.json()["enabled"] is True

        # 清理
        await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_delete_server(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除服务器"""
        # Arrange - 创建服务器
        server_data = {
            "name": "delete-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        create_response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        server_id = create_response.json()["id"]

        # Act - 删除服务器
        delete_response = await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

        # Assert
        assert delete_response.status_code == status.HTTP_200_OK
        assert delete_response.json()["message"] == "Server deleted successfully"

        # 验证服务器已删除 - 通过列表查询
        list_response = await client.get("/api/v1/mcp/servers", headers=auth_headers)
        user_servers = list_response.json()["user_servers"]
        server_ids = [s["id"] for s in user_servers]
        assert server_id not in server_ids

    @pytest.mark.asyncio
    async def test_update_server(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 更新服务器配置"""
        # Arrange - 创建服务器
        server_data = {
            "name": "update-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
            "display_name": "Original Name",
        }

        create_response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        server_id = create_response.json()["id"]

        # Act - 更新服务器
        update_data = {
            "display_name": "Updated Name",
            "enabled": False,
        }

        update_response = await client.put(
            f"/api/v1/mcp/servers/{server_id}",
            json=update_data,
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["display_name"] == "Updated Name"
        assert data["enabled"] is False

        # 清理
        await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_test_connection(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 测试服务器连接"""
        # Arrange - 创建服务器
        server_data = {
            "name": "connection-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        create_response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        server_id = create_response.json()["id"]

        # Act
        test_response = await client.post(
            f"/api/v1/mcp/servers/{server_id}/test",
            headers=auth_headers,
        )

        # Assert
        assert test_response.status_code == status.HTTP_200_OK
        data = test_response.json()
        assert "success" in data
        assert "server_name" in data
        assert "server_url" in data

        # 清理
        await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )


class TestMCPPermissionsAPI:
    """MCP 权限 API 集成测试"""

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_user_scope_servers(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """测试: 用户只能看到自己创建的用户级服务器"""
        # Arrange - 创建两个用户级服务器
        server1_data = {
            "name": "user-server-1",
            "url": "stdio://test1",
            "env_type": "dynamic_injected",
            "env_config": {},
        }
        server2_data = {
            "name": "user-server-2",
            "url": "stdio://test2",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        response1 = await client.post(
            "/api/v1/mcp/servers",
            json=server1_data,
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_201_CREATED
        server1_id = response1.json()["id"]

        response2 = await client.post(
            "/api/v1/mcp/servers",
            json=server2_data,
            headers=auth_headers,
        )
        assert response2.status_code == status.HTTP_201_CREATED
        server2_id = response2.json()["id"]

        # Act - 获取服务器列表
        list_response = await client.get(
            "/api/v1/mcp/servers",
            headers=auth_headers,
        )

        # Assert - 应该看到系统级服务器和自己的用户级服务器
        assert list_response.status_code == status.HTTP_200_OK
        data = list_response.json()
        user_servers = data["user_servers"]
        server_ids = [s["id"] for s in user_servers]

        assert server1_id in server_ids
        assert server2_id in server_ids

        # 验证 scope 正确
        for server in user_servers:
            assert server["scope"] == "user"
            assert server["user_id"] == str(test_user.id)

        # 清理
        await client.delete(
            f"/api/v1/mcp/servers/{server1_id}",
            headers=auth_headers,
        )
        await client.delete(
            f"/api/v1/mcp/servers/{server2_id}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_user_cannot_delete_system_servers(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 普通用户不能删除系统级服务器"""
        # Arrange - 获取系统级服务器的 ID
        list_response = await client.get("/api/v1/mcp/servers", headers=auth_headers)
        system_servers = list_response.json()["system_servers"]
        assert len(system_servers) > 0, "应该有系统级服务器"
        system_server_id = system_servers[0]["id"]

        # Act - 尝试删除系统级服务器
        delete_response = await client.delete(
            f"/api/v1/mcp/servers/{system_server_id}",
            headers=auth_headers,
        )

        # Assert - 应该失败（403 Forbidden，因为权限不足）
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_user_cannot_update_system_servers(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 普通用户不能更新系统级服务器"""
        # Arrange - 获取系统级服务器的 ID
        list_response = await client.get("/api/v1/mcp/servers", headers=auth_headers)
        system_servers = list_response.json()["system_servers"]
        assert len(system_servers) > 0, "应该有系统级服务器"
        system_server_id = system_servers[0]["id"]
        update_data = {"display_name": "Hacked System Server"}

        # Act - 尝试更新系统级服务器
        update_response = await client.put(
            f"/api/v1/mcp/servers/{system_server_id}",
            json=update_data,
            headers=auth_headers,
        )

        # Assert - 应该失败（403 Forbidden，因为权限不足）
        assert update_response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_create_user_scope_server_has_correct_user_id(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """测试: 创建用户级服务器时正确设置 user_id"""
        # Arrange
        server_data = {
            "name": "user-ownership-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        # Act
        response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_id"] == str(test_user.id)
        assert data["scope"] == "user"

        # 清理
        await client.delete(
            f"/api/v1/mcp/servers/{data['id']}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_system_servers_visible_to_all_users(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 系统级服务器对所有用户可见"""
        # Act
        response = await client.get(
            "/api/v1/mcp/servers",
            headers=auth_headers,
        )

        # Assert - 应该能看到系统级服务器（由迁移添加）
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        system_servers = data["system_servers"]

        # 验证系统级服务器存在
        assert len(system_servers) > 0

        # 验证系统级服务器的属性
        for server in system_servers:
            assert server["scope"] == "system"
            assert server["user_id"] is None

    @pytest.mark.asyncio
    async def test_user_can_only_delete_own_servers(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """测试: 用户只能删除自己创建的服务器"""
        # Arrange - 创建服务器
        server_data = {
            "name": "delete-ownership-test",
            "url": "stdio://test",
            "env_type": "dynamic_injected",
            "env_config": {},
        }

        create_response = await client.post(
            "/api/v1/mcp/servers",
            json=server_data,
            headers=auth_headers,
        )
        server_id = create_response.json()["id"]

        # Act - 删除自己的服务器（应该成功）
        delete_response = await client.delete(
            f"/api/v1/mcp/servers/{server_id}",
            headers=auth_headers,
        )

        # Assert
        assert delete_response.status_code == status.HTTP_200_OK

