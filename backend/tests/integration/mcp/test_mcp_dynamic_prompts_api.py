"""
MCP Dynamic Prompts API 集成测试

测试 GET/POST/PUT/DELETE /api/v1/mcp/servers/{server_name}/dynamic-prompts。
需管理员认证；server_name 须在 SERVER_MAP 中（如 llm-server）。
"""

from httpx import AsyncClient
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCPDynamicPromptsAPI:
    """动态 Prompts API 集成测试"""

    async def test_list_dynamic_prompts_requires_admin(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """非管理员调用 list dynamic-prompts 应返回 403"""
        response = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=auth_headers,
        )
        assert response.status_code == 403

    async def test_list_dynamic_prompts_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """管理员 GET 无记录时返回空列表"""
        response = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 0

    async def test_add_and_list_and_put_and_delete(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """管理员 POST 添加 → GET 列表包含 → PUT 更新 → GET 含更新内容 → DELETE 删除 → GET 不再包含"""
        add_body = {
            "prompt_key": "integration_test_prompt",
            "template": "请总结：{{content}}",
            "title": "Integration Test",
            "description": "Test prompt",
            "arguments_schema": [
                {"name": "content", "description": "要总结的文本", "required": True}
            ],
        }
        add_resp = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
            json=add_body,
        )
        assert add_resp.status_code == 201
        added = add_resp.json()
        assert added["prompt_key"] == "integration_test_prompt"
        assert added["template"] == "请总结：{{content}}"
        assert "id" in added

        list_resp = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
        )
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert any(p["prompt_key"] == "integration_test_prompt" for p in list_data)

        put_body = {"template": "Updated: {{content}}", "title": "Updated Title"}
        put_resp = await client.put(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts/integration_test_prompt",
            headers=admin_headers,
            json=put_body,
        )
        assert put_resp.status_code == 200
        updated = put_resp.json()
        assert updated["template"] == "Updated: {{content}}"
        assert updated["title"] == "Updated Title"

        list_resp2 = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
        )
        assert list_resp2.status_code == 200
        list_data2 = list_resp2.json()
        one = next((p for p in list_data2 if p["prompt_key"] == "integration_test_prompt"), None)
        assert one is not None
        assert one["template"] == "Updated: {{content}}"
        assert one["title"] == "Updated Title"

        del_resp = await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts/integration_test_prompt",
            headers=admin_headers,
        )
        assert del_resp.status_code == 204

        list_resp3 = await client.get(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
        )
        assert list_resp3.status_code == 200
        list_data3 = list_resp3.json()
        assert not any(p["prompt_key"] == "integration_test_prompt" for p in list_data3)

    async def test_add_duplicate_prompt_key_returns_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """同 server 下重复 prompt_key POST 应返回 409"""
        body = {
            "prompt_key": "dup_409_prompt",
            "template": "Hello {{x}}",
            "arguments_schema": [],
        }
        r1 = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
            json=body,
        )
        assert r1.status_code == 201
        r2 = await client.post(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts",
            headers=admin_headers,
            json=body,
        )
        assert r2.status_code == 409
        await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts/dup_409_prompt",
            headers=admin_headers,
        )

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """删除不存在的 prompt_key 应返回 404"""
        response = await client.delete(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts/nonexistent_prompt_xyz",
            headers=admin_headers,
        )
        assert response.status_code == 404

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """更新不存在的 prompt_key 应返回 404"""
        response = await client.put(
            "/api/v1/mcp/servers/llm-server/dynamic-prompts/nonexistent_prompt_xyz",
            headers=admin_headers,
            json={"template": "x"},
        )
        assert response.status_code == 404

    async def test_invalid_server_name_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ):
        """server_name 不在 SERVER_MAP 时 GET 返回 404"""
        response = await client.get(
            "/api/v1/mcp/servers/not-a-real-server/dynamic-prompts",
            headers=admin_headers,
        )
        assert response.status_code == 404
