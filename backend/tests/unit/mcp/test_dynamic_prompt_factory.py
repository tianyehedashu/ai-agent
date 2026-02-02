"""
MCP Dynamic Prompt Factory 单元测试

验证 build_prompt 根据 template + arguments_schema 生成 MCP Prompt 实例，
渲染后返回符合 MCP 的 messages 结构（UserMessage + TextContent）。
"""

import pytest

from domains.agent.infrastructure.mcp_server.dynamic_prompt_factory import build_prompt


class TestBuildPrompt:
    """build_prompt 测试"""

    def test_returns_prompt_instance(self):
        """应返回 MCP Prompt 实例"""
        p = build_prompt(
            name="test",
            template="Hello {{name}}",
            title="Test",
            arguments_schema=[{"name": "name", "description": "Name", "required": True}],
        )
        assert p is not None
        assert p.name == "test"
        assert p.title == "Test"

    def test_invalid_arguments_schema_raises(self):
        """arguments_schema 项缺少 name 时应抛出 ValueError"""
        with pytest.raises(ValueError, match="Invalid arguments_schema"):
            build_prompt(
                name="x",
                template="x",
                arguments_schema=[{"description": "no name"}],
            )

    @pytest.mark.asyncio
    async def test_render_produces_user_message(self):
        """渲染后应返回 UserMessage，content 为 TextContent"""
        p = build_prompt(
            name="summarize",
            template="请总结：{{content}}",
            arguments_schema=[{"name": "content", "description": "要总结的文本", "required": True}],
        )
        # fn 是 async，接收 **kwargs
        result = await p.fn(content="这是一段文字")
        assert result.role == "user"
        assert hasattr(result, "content")
        assert result.content.type == "text"
        assert "请总结：" in result.content.text
        assert "这是一段文字" in result.content.text

    @pytest.mark.asyncio
    async def test_render_placeholder_replaced(self):
        """占位符 {{key}} 应被替换为 arguments 中的值"""
        p = build_prompt(
            name="greet",
            template="Hello {{name}}, style: {{style}}",
            arguments_schema=[
                {"name": "name", "required": True},
                {"name": "style", "required": False},
            ],
        )
        result = await p.fn(name="World", style="friendly")
        assert "World" in result.content.text
        assert "friendly" in result.content.text

    @pytest.mark.asyncio
    async def test_render_empty_arguments_schema(self):
        """无 arguments_schema 时仍可渲染（无占位符替换）"""
        p = build_prompt(name="fixed", template="Fixed text only", arguments_schema=[])
        result = await p.fn()
        assert result.content.text == "Fixed text only"
