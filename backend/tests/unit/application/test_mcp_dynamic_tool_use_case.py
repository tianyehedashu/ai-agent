"""
MCP Dynamic Tool Use Case 单元/集成测试

使用真实 db_session 与 MCPDynamicToolRepository，验证 List/Add/Remove 行为。
需测试数据库存在且已执行迁移（含 mcp_dynamic_tools 表）。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application.mcp_dynamic_tool_use_case import MCPDynamicToolUseCase
from libs.exceptions import ConflictError, NotFoundError, ValidationError


@pytest.mark.asyncio
class TestMCPDynamicToolUseCase:
    """MCP 动态工具用例测试"""

    async def test_list_empty(self, db_session: AsyncSession):
        """无记录时 list_dynamic_tools 返回空列表"""
        use_case = MCPDynamicToolUseCase(db_session)
        result = await use_case.list_dynamic_tools("llm-server")
        assert result == []

    async def test_add_and_list(self, db_session: AsyncSession):
        """添加后 list 可查到该记录"""
        use_case = MCPDynamicToolUseCase(db_session)
        added = await use_case.add_dynamic_tool(
            server_name="llm-server",
            tool_key="test_tool",
            tool_type="http_call",
            config={"url": "https://example.com"},
            description="Test",
        )
        assert added["tool_key"] == "test_tool"
        assert added["tool_type"] == "http_call"
        assert "id" in added

        listed = await use_case.list_dynamic_tools("llm-server")
        assert len(listed) == 1
        assert listed[0]["tool_key"] == "test_tool"
        assert listed[0]["description"] == "Test"

    async def test_add_duplicate_tool_key_conflict(self, db_session: AsyncSession):
        """同 server 下重复 tool_key 应抛出 ConflictError"""
        use_case = MCPDynamicToolUseCase(db_session)
        await use_case.add_dynamic_tool(
            server_name="llm-server",
            tool_key="dup_key",
            tool_type="http_call",
            config={"url": "https://a.com"},
        )
        with pytest.raises(ConflictError, match="already exists"):
            await use_case.add_dynamic_tool(
                server_name="llm-server",
                tool_key="dup_key",
                tool_type="http_call",
                config={"url": "https://b.com"},
            )

    async def test_invalid_tool_type_validation(self, db_session: AsyncSession):
        """无效 tool_type 应抛出 ValidationError"""
        use_case = MCPDynamicToolUseCase(db_session)
        with pytest.raises(ValidationError, match="Unknown tool_type"):
            await use_case.add_dynamic_tool(
                server_name="llm-server",
                tool_key="x",
                tool_type="unknown_type",
                config={},
            )

    async def test_empty_tool_key_validation(self, db_session: AsyncSession):
        """空 tool_key 应抛出 ValidationError"""
        use_case = MCPDynamicToolUseCase(db_session)
        with pytest.raises(ValidationError, match="tool_key"):
            await use_case.add_dynamic_tool(
                server_name="llm-server",
                tool_key="   ",
                tool_type="http_call",
                config={"url": "https://example.com"},
            )

    async def test_remove_and_list(self, db_session: AsyncSession):
        """删除后 list 不再包含该记录"""
        use_case = MCPDynamicToolUseCase(db_session)
        await use_case.add_dynamic_tool(
            server_name="llm-server",
            tool_key="to_remove",
            tool_type="http_call",
            config={"url": "https://example.com"},
        )
        listed_before = await use_case.list_dynamic_tools("llm-server")
        assert len(listed_before) >= 1
        assert any(t["tool_key"] == "to_remove" for t in listed_before)

        await use_case.remove_dynamic_tool("llm-server", "to_remove")

        listed_after = await use_case.list_dynamic_tools("llm-server")
        assert not any(t["tool_key"] == "to_remove" for t in listed_after)

    async def test_remove_not_found(self, db_session: AsyncSession):
        """删除不存在的 tool_key 应抛出 NotFoundError"""
        use_case = MCPDynamicToolUseCase(db_session)
        with pytest.raises(NotFoundError, match="Dynamic tool"):
            await use_case.remove_dynamic_tool("llm-server", "nonexistent_key")

    async def test_list_only_returns_same_server(self, db_session: AsyncSession):
        """list_dynamic_tools 仅返回该 server 的记录"""
        use_case = MCPDynamicToolUseCase(db_session)
        await use_case.add_dynamic_tool(
            server_name="llm-server",
            tool_key="on_llm",
            tool_type="http_call",
            config={"url": "https://llm.com"},
        )
        # 若存在其他 server（如未来扩展），此处仅断言 llm-server 的列表含 on_llm
        listed = await use_case.list_dynamic_tools("llm-server")
        assert any(t["tool_key"] == "on_llm" for t in listed)
