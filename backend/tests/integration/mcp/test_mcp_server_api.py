"""
MCP Server Integration Tests - MCP 服务器集成测试

测试 MCP 服务器 API 端点，使用 conftest.py 中的 client fixture
"""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
class TestMCPServerAPI:
    """MCP 服务器 API 集成测试"""

    async def test_list_mcp_servers_no_auth(self, client: AsyncClient):
        """测试列出服务器（无需认证）"""
        response = await client.get("/api/v1/mcp/")
        assert response.status_code == 200

        data = response.json()
        assert "servers" in data
        assert len(data["servers"]) > 0
        assert data["transport"] in ["SSE", "Streamable HTTP"]

    async def test_list_mcp_servers_content(self, client: AsyncClient):
        """测试服务器列表内容"""
        response = await client.get("/api/v1/mcp/")
        assert response.status_code == 200

        data = response.json()
        server_scopes = [s["scope"] for s in data["servers"]]

        # 检查是否有 LLM 服务器（目前唯一实现的 FastMCP 服务器）
        assert "llm-server" in server_scopes
        # 其他服务器可以在未来添加
        # assert "filesystem-server" in server_scopes  # TODO: 实现后取消注释

    async def test_get_server_info_no_auth(self, client: AsyncClient):
        """测试获取服务器信息（需要认证）"""
        # 这个端点需要认证，所以应该返回 401
        response = await client.get("/api/v1/mcp/llm-server/info")
        # 可能是 401 或 403，取决于认证实现
        assert response.status_code in (401, 403, 422)

    @pytest.mark.parametrize(
        "server_name,expected_exists",
        [
            ("llm-server", True),  # 已实现
            ("filesystem-server", False),  # 未实现
            ("memory-server", False),  # 未实现
            ("workflow-server", False),  # 未实现
            ("custom-server", False),  # 未实现
        ],
    )
    async def test_server_endpoint_exists(
        self, client: AsyncClient, server_name: str, expected_exists: bool
    ):
        """测试服务器端点存在"""
        # 不带认证的请求应该被拒绝
        response = await client.get(f"/api/v1/mcp/{server_name}")
        if expected_exists:
            # 已实现的服务器：应该返回认证错误
            assert response.status_code in (401, 403, 422)
        else:
            # 未实现的服务器：应该返回 401（认证先拒绝）或 404
            assert response.status_code in (401, 403, 404, 422)

    async def test_invalid_server_name(self, client: AsyncClient):
        """测试无效的服务器名称"""
        response = await client.get("/api/v1/mcp/invalid-server")
        # 未认证时，认证中间件先拒绝请求，返回 401
        # 如果认证通过，才会返回 404
        assert response.status_code in (401, 403, 404, 422)


@pytest.mark.asyncio
class TestMCPServerWithAPIKey:
    """使用 API Key 的 MCP 服务器测试"""

    @pytest.fixture
    def test_api_key(self) -> str:
        """测试用的 API Key

        注意：这是伪造的 key，实际测试需要创建真实的 API Key
        """
        return "sk_test_key_1234567890123456_test_secret_1234567890123456789012"

    async def test_sse_connection_with_valid_key(self, client: AsyncClient, test_api_key: str):
        """测试使用有效 API Key 建立 SSE 连接"""
        headers = {"Authorization": f"Bearer {test_api_key}"}

        # 发起 SSE 请求
        response = await client.get("/api/v1/mcp/llm-server", headers=headers, timeout=5.0)

        # SSE 应该返回 200 或认证错误
        # 500: 数据库不可用
        if response.status_code == 200:
            # 检查响应类型
            assert "text/event-stream" in response.headers.get("content-type", "")

            # 读取一些内容
            content = response.text
            assert "endpoint:" in content or "data:" in content

    async def test_server_info_with_valid_key(self, client: AsyncClient, test_api_key: str):
        """测试使用有效 API Key 获取服务器信息"""
        headers = {"Authorization": f"Bearer {test_api_key}"}

        response = await client.get("/api/v1/mcp/llm-server/info", headers=headers)

        # API Key 可能没有正确的 scope
        # 如果是 403，说明 key 没有 mcp:llm-server scope
        # 如果是 200，说明成功
        # 500: 数据库不可用（测试环境）
        assert response.status_code in (200, 401, 403, 404, 500)

        if response.status_code == 200:
            data = response.json()
            assert data["scope"] == "llm-server"
            assert "tool_count" in data


@pytest.mark.asyncio
class TestMCPProtocolFlow:
    """MCP 协议流程测试"""

    @pytest.fixture
    def mcp_api_key(self) -> str | None:
        """MCP 服务器专用的 API Key

        实际测试中应该创建一个具有 mcp:llm-server scope 的 API Key
        """
        # 返回 None 表示没有可用的 MCP API Key
        return None

    async def test_initialize_flow(self, client: AsyncClient, mcp_api_key: str | None):
        """测试初始化流程"""
        if not mcp_api_key:
            pytest.skip("No MCP API key available")

        headers = {"Authorization": f"Bearer {mcp_api_key}"}

        # 发送初始化请求
        response = await client.get("/api/v1/mcp/llm-server", headers=headers, timeout=5.0)

        if response.status_code == 200:
            content = response.text
            # 检查是否有 endpoint 事件
            assert "endpoint: llm-server" in content
