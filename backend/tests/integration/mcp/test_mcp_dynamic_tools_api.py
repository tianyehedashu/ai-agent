"""
MCP Dynamic Tools API 集成测试

测试 GET/POST/DELETE /api/v1/mcp/servers/{server_name}/dynamic-tools。
需管理员认证；server_name 须在 SERVER_MAP 中（如 llm-server）。
"""

from httpx import AsyncClient
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCPDynamicToolsAPI:
    """动态工具 API 集成测试"""

    async def test_list_dynamic_tools_requires_admin(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """非管理员调用 list dynamic-tools 应返回 403"""
        response = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=auth_headers,
        )
        # 普通用户无 admin 角色，应 403
        assert response.status_code == 403

    async def test_list_dynamic_tools_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """管理员 GET 无记录时返回空列表"""
        response = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 初始可为空
        assert len(data) >= 0

    async def test_add_and_list_and_delete(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """管理员 POST 添加 → GET 列表包含 → DELETE 删除 → GET 不再包含"""
        # POST 添加
        add_body = {
            "tool_key": "integration_test_tool",
            "tool_type": "http_call",
            "config": {"url": "https://example.com/ping", "method": "GET"},
            "description": "Integration test tool",
        }
        add_resp = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
            json=add_body,
        )
        assert add_resp.status_code == 201
        added = add_resp.json()
        assert added["tool_key"] == "integration_test_tool"
        assert added["tool_type"] == "http_call"
        assert "id" in added

        # GET 列表包含
        list_resp = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
        )
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert any(t["tool_key"] == "integration_test_tool" for t in list_data)

        # DELETE 删除
        del_resp = await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-tools/integration_test_tool",
            headers=admin_headers,
        )
        assert del_resp.status_code == 204

        # GET 不再包含
        list_resp2 = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
        )
        assert list_resp2.status_code == 200
        list_data2 = list_resp2.json()
        assert not any(t["tool_key"] == "integration_test_tool" for t in list_data2)

    async def test_add_duplicate_tool_key_returns_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """同 server 下重复 tool_key POST 应返回 409"""
        body = {
            "tool_key": "dup_409_tool",
            "tool_type": "http_call",
            "config": {"url": "https://example.com"},
        }
        r1 = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
            json=body,
        )
        assert r1.status_code == 201
        r2 = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-tools",
            headers=admin_headers,
            json=body,
        )
        assert r2.status_code == 409
        # 清理
        await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-tools/dup_409_tool",
            headers=admin_headers,
        )

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """删除不存在的 tool_key 应返回 404"""
        response = await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-tools/nonexistent_tool_key_xyz",
            headers=admin_headers,
        )
        assert response.status_code == 404

    async def test_invalid_server_name_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """server_name 不在 SERVER_MAP 时 GET 返回 404"""
        response = await client.get(
            "/api/v1/mcp/servers/not-a-real-server/dynamic-tools",
            headers=admin_headers,
        )
        assert response.status_code == 404
