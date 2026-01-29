"""
MCP Tool Service Unit Tests - MCP 工具服务单元测试

测试 URL 解析和工具服务功能
"""

from domains.agent.infrastructure.tools.mcp.tool_service import parse_url_to_connection


class TestParseUrlToConnection:
    """URL 解析测试"""

    def test_parse_stdio_url_simple(self):
        """测试解析 stdio URL（简单命令）"""
        url = "stdio://npx"
        result = parse_url_to_connection(url)

        # StdioConnection 有 command 和 args 键
        assert "command" in result
        assert result["command"] == "npx"
        assert result["args"] == []

    def test_parse_stdio_url_with_args(self):
        """测试解析 stdio URL（带参数）"""
        url = "stdio://npx -y @modelcontextprotocol/server-filesystem"
        result = parse_url_to_connection(url)

        assert "command" in result
        assert result["command"] == "npx"
        assert result["args"] == ["-y", "@modelcontextprotocol/server-filesystem"]

    def test_parse_stdio_url_with_env_config(self):
        """测试解析 stdio URL（带环境配置）"""
        url = "stdio://python script.py"
        env_config = {
            "env": {"CUSTOM_VAR": "value"},
            "cwd": "/workspace",
        }
        result = parse_url_to_connection(url, env_config)

        assert "command" in result
        assert result["command"] == "python"
        assert result["args"] == ["script.py"]
        assert result["env"] == {"CUSTOM_VAR": "value"}
        assert result["cwd"] == "/workspace"

    def test_parse_sse_url(self):
        """测试解析 SSE URL"""
        url = "sse://localhost:8080/mcp"
        result = parse_url_to_connection(url)

        # SSEConnection 有 url 键但没有 command 键
        assert "url" in result
        assert "command" not in result
        assert result["url"] == "https://localhost:8080/mcp"

    def test_parse_sse_url_with_headers(self):
        """测试解析 SSE URL（带自定义头）"""
        url = "sse://api.example.com/mcp"
        env_config = {"headers": {"Authorization": "Bearer token123"}}
        result = parse_url_to_connection(url, env_config)

        assert "url" in result
        assert result["url"] == "https://api.example.com/mcp"
        assert result["headers"] == {"Authorization": "Bearer token123"}

    def test_parse_http_url(self):
        """测试解析 HTTP URL"""
        url = "http://localhost:8080/mcp"
        result = parse_url_to_connection(url)

        # StreamableHttpConnection 有 url 键
        assert "url" in result
        assert "command" not in result
        assert result["url"] == "http://localhost:8080/mcp"

    def test_parse_https_url(self):
        """测试解析 HTTPS URL"""
        url = "https://api.example.com/mcp"
        result = parse_url_to_connection(url)

        assert "url" in result
        assert result["url"] == "https://api.example.com/mcp"

    def test_parse_http_url_with_headers(self):
        """测试解析 HTTP URL（带自定义头）"""
        url = "https://api.example.com/mcp"
        env_config = {"headers": {"X-API-Key": "secret"}}
        result = parse_url_to_connection(url, env_config)

        assert "url" in result
        assert result["url"] == "https://api.example.com/mcp"
        assert result["headers"] == {"X-API-Key": "secret"}

    def test_parse_websocket_url(self):
        """测试解析 WebSocket URL"""
        url = "ws://localhost:8080/mcp"
        result = parse_url_to_connection(url)

        # WebsocketConnection 有 url 键
        assert "url" in result
        assert result["url"] == "ws://localhost:8080/mcp"

    def test_parse_secure_websocket_url(self):
        """测试解析安全 WebSocket URL"""
        url = "wss://api.example.com/mcp"
        result = parse_url_to_connection(url)

        assert "url" in result
        assert result["url"] == "wss://api.example.com/mcp"

    def test_parse_websocket_url_with_headers(self):
        """测试解析 WebSocket URL（带自定义头）"""
        url = "ws://localhost:8080/mcp"
        env_config = {"headers": {"Authorization": "Bearer token123"}}
        result = parse_url_to_connection(url, env_config)

        assert "url" in result
        assert result["url"] == "ws://localhost:8080/mcp"
        assert result["headers"] == {"Authorization": "Bearer token123"}

    def test_parse_secure_websocket_url_with_headers(self):
        """测试解析安全 WebSocket URL（带自定义头）"""
        url = "wss://api.example.com/mcp"
        env_config = {"headers": {"X-API-Key": "secret", "Authorization": "Bearer token"}}
        result = parse_url_to_connection(url, env_config)

        assert "url" in result
        assert result["url"] == "wss://api.example.com/mcp"
        assert result["headers"] == {"X-API-Key": "secret", "Authorization": "Bearer token"}

    def test_parse_url_with_none_env_config(self):
        """测试解析 URL（env_config 为 None）"""
        url = "http://localhost:8080/mcp"
        result = parse_url_to_connection(url, None)

        assert "url" in result
        assert result["url"] == "http://localhost:8080/mcp"

    def test_parse_complex_stdio_url(self):
        """测试解析复杂 stdio URL"""
        url = "stdio://uvx mcp-server-git --repository /path/to/repo"
        result = parse_url_to_connection(url)

        assert "command" in result
        assert result["command"] == "uvx"
        assert result["args"] == ["mcp-server-git", "--repository", "/path/to/repo"]

    def test_parse_stdio_returns_stdio_connection(self):
        """测试 stdio URL 返回正确的连接类型"""
        url = "stdio://npx -y @modelcontextprotocol/server-filesystem"
        result = parse_url_to_connection(url)

        # 验证是 stdio 类型（有 command 键）
        assert "command" in result
        assert "args" in result
        # 不应有 url 键
        # Note: StdioConnection 没有 url 键

    def test_parse_http_returns_http_connection(self):
        """测试 HTTP URL 返回正确的连接类型"""
        url = "http://localhost:8080/mcp"
        result = parse_url_to_connection(url)

        # 验证是 HTTP 类型（有 url 键但没有 command 键）
        assert "url" in result
        assert "command" not in result

    def test_parse_ws_returns_websocket_connection(self):
        """测试 WebSocket URL 返回正确的连接类型"""
        url = "ws://localhost:8080/mcp"
        result = parse_url_to_connection(url)

        # WebSocket 连接也有 url 键
        assert "url" in result
        assert result["url"].startswith("ws://")
