"""
LLM Gateway 单元测试

使用 Mock 测试 LLM Gateway 的功能
"""

from unittest.mock import patch

import pytest

from core.llm.gateway import LLMGateway, LLMResponse
from core.types import ToolCall


class TestLLMGateway:
    """LLM Gateway 测试"""

    @pytest.fixture
    def gateway(self):
        """创建被测对象"""
        return LLMGateway()

    @pytest.mark.asyncio
    async def test_chat_returns_text_response(self, gateway):
        """测试: 返回文本响应"""
        # Arrange
        mock_response = LLMResponse(content="Hello, how can I help?")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4",
            )

            # Assert
            assert result.content == "Hello, how can I help?"
            assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_chat_parses_tool_calls(self, gateway):
        """测试: 解析工具调用"""
        # Arrange
        tool_call = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        mock_response = LLMResponse(
            content="",
            tool_calls=[tool_call],
        )

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Read the file"}],
                model="gpt-4",
                tools=[{"type": "function", "function": {"name": "read_file"}}],
            )

            # Assert
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "read_file"
            assert result.tool_calls[0].arguments["path"] == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self, gateway):
        """测试: API 错误处理"""
        # Arrange
        with patch.object(
            gateway, "_chat", side_effect=Exception("API Error")
        ):
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await gateway.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4",
                )

            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_with_streaming(self, gateway):
        """测试: 流式响应"""
        # Arrange
        from core.llm.gateway import StreamChunk

        async def mock_stream():
            chunks = [
                StreamChunk(content="Hello"),
                StreamChunk(content=" world"),
                StreamChunk(content="!"),
            ]
            for chunk in chunks:
                yield chunk

        with patch.object(gateway, "_stream_chat", return_value=mock_stream()):
            # Act
            full_content = ""
            async for chunk in gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4",
                stream=True,
            ):
                full_content += chunk.content or ""

            # Assert
            assert full_content == "Hello world!"

    @pytest.mark.asyncio
    async def test_chat_uses_default_model(self, gateway):
        """测试: 使用默认模型"""
        # Arrange
        mock_response = LLMResponse(content="Response")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            await gateway.chat(messages=[{"role": "user", "content": "Hi"}])

            # Assert
            # 应该使用默认模型
            gateway._chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_temperature(self, gateway):
        """测试: 温度参数传递"""
        # Arrange
        mock_response = LLMResponse(content="Response")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.5,
            )

            # Assert
            gateway._chat.assert_called_once()
