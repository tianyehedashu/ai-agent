"""
File Tools Tests - 文件工具测试
"""

import pytest

from domains.agent.infrastructure.tools.file_tools import ListDirTool, ReadFileTool


@pytest.mark.asyncio
async def test_read_file_not_found() -> None:
    """测试读取不存在的文件"""
    tool = ReadFileTool()
    result = await tool.execute(path="/nonexistent/file.txt")

    assert not result.success
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_list_dir_not_found() -> None:
    """测试列出不存在的目录"""
    tool = ListDirTool()
    result = await tool.execute(path="/nonexistent/directory")

    assert not result.success
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_openai_format() -> None:
    """测试工具转换为 OpenAI 格式"""
    tool = ReadFileTool()
    openai_tool = tool.to_openai_tool()

    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "read_file"
    assert "description" in openai_tool["function"]
    assert "parameters" in openai_tool["function"]


@pytest.mark.asyncio
async def test_tool_anthropic_format() -> None:
    """测试工具转换为 Anthropic 格式"""
    tool = ReadFileTool()
    anthropic_tool = tool.to_anthropic_tool()

    assert anthropic_tool["name"] == "read_file"
    assert "description" in anthropic_tool
    assert "input_schema" in anthropic_tool
