"""
MCP Dynamic Tool Factory 单元测试

验证 build_tool_fn 根据 tool_type 与 config 生成可调用的 async 函数。
闭包内 import httpx，测试通过 patch sys.modules['httpx'] 模拟。
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domains.agent.domain.mcp.dynamic_tool import DynamicToolType
from domains.agent.infrastructure.mcp_server.dynamic_tool_factory import (
    build_http_call_fn,
    build_tool_fn,
)


def _make_httpx_mock(response_text: str = "ok"):
    """构造 mock httpx 模块，闭包内 import httpx 会从 sys.modules 取"""
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client
    return mock_httpx, mock_client


class TestBuildHttpCallFn:
    """build_http_call_fn 测试"""

    @pytest.mark.asyncio
    async def test_returns_async_callable(self):
        """返回的函数应是可 await 的 async 函数"""
        fn = build_http_call_fn({"url": "https://httpbin.org/get", "method": "GET"})
        assert callable(fn)

    @pytest.mark.asyncio
    async def test_http_call_get_makes_request(self):
        """http_call GET 请求：mock httpx 断言 url/method"""
        mock_httpx, mock_client = _make_httpx_mock("ok")
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            fn = build_http_call_fn({"url": "https://example.com/api", "method": "GET"})
            result = await fn()
            assert result == "ok"
            mock_client.get.assert_called_once_with("https://example.com/api", headers=None)

    @pytest.mark.asyncio
    async def test_http_call_post_with_body(self):
        """http_call POST 请求：config 中 body 作为默认 body"""
        mock_httpx, mock_client = _make_httpx_mock("created")
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            fn = build_http_call_fn(
                {
                    "url": "https://example.com/api",
                    "method": "POST",
                    "body": {"key": "value"},
                }
            )
            result = await fn()
            assert result == "created"
            mock_client.post.assert_called_once()
            call_kw = mock_client.post.call_args[1]
            assert call_kw.get("json") == {"key": "value"}

    @pytest.mark.asyncio
    async def test_http_call_headers_from_config(self):
        """http_call 使用 config 中的 headers"""
        mock_httpx, mock_client = _make_httpx_mock("ok")
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            fn = build_http_call_fn(
                {
                    "url": "https://example.com/api",
                    "method": "GET",
                    "headers": {"X-Custom": "test"},
                }
            )
            await fn()
            mock_client.get.assert_called_once()
            call_kw = mock_client.get.call_args[1]
            assert call_kw.get("headers") == {"X-Custom": "test"}


class TestBuildToolFn:
    """build_tool_fn 测试"""

    def test_http_call_requires_url(self):
        """http_call 类型缺少 url 时应抛出 ValueError"""
        with pytest.raises(ValueError, match=r"http_call requires config\.url"):
            build_tool_fn(DynamicToolType.HTTP_CALL.value, {"method": "GET"})

    def test_unknown_tool_type_raises(self):
        """未知 tool_type 应抛出 ValueError"""
        with pytest.raises(ValueError, match="Unknown dynamic tool type"):
            build_tool_fn("unknown_type", {})

    def test_http_call_returns_callable(self):
        """http_call 合法 config 应返回可调用对象"""
        fn = build_tool_fn(
            DynamicToolType.HTTP_CALL.value,
            {"url": "https://example.com"},
        )
        assert callable(fn)

    @pytest.mark.asyncio
    async def test_http_call_integration_mock(self):
        """build_tool_fn('http_call', config) 生成的函数可正常请求"""
        mock_httpx, mock_client = _make_httpx_mock("pong")
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            fn = build_tool_fn(
                "http_call",
                {"url": "https://api.test/ping", "method": "GET"},
            )
            out = await fn()
            assert out == "pong"
            mock_client.get.assert_called_once_with("https://api.test/ping", headers=None)
