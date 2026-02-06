"""
MCP Dynamic Prompt Use Case 单元测试

使用真实 db_session 与 MCPDynamicPromptRepository，验证 List/Add/Update/Remove 行为。
需测试数据库存在且已执行迁移（含 mcp_dynamic_prompts 表）。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application.mcp_dynamic_prompt_use_case import MCPDynamicPromptUseCase
from exceptions import ConflictError, NotFoundError, ValidationError


@pytest.mark.asyncio
class TestMCPDynamicPromptUseCase:
    """MCP 动态 Prompt 用例测试"""

    async def test_list_empty(self, db_session: AsyncSession):
        """无记录时 list_dynamic_prompts 返回空列表（用无 seed 的 server_id）"""
        use_case = MCPDynamicPromptUseCase(db_session)
        result = await use_case.list_dynamic_prompts("no-prompts-server")
        assert result == []

    async def test_add_and_list(self, db_session: AsyncSession):
        """添加后 list 可查到该记录"""
        use_case = MCPDynamicPromptUseCase(db_session)
        added = await use_case.add_dynamic_prompt(
            server_name="llm-server",
            prompt_key="test_prompt",
            template="请总结：{{content}}",
            title="Test",
            description="Test prompt",
        )
        assert added["prompt_key"] == "test_prompt"
        assert added["template"] == "请总结：{{content}}"
        assert "id" in added

        listed = await use_case.list_dynamic_prompts("llm-server")
        assert len(listed) >= 1
        one = next((p for p in listed if p["prompt_key"] == "test_prompt"), None)
        assert one is not None
        assert one["title"] == "Test"
        assert one["description"] == "Test prompt"

    async def test_add_duplicate_prompt_key_conflict(self, db_session: AsyncSession):
        """同 server 下重复 prompt_key 应抛出 ConflictError"""
        use_case = MCPDynamicPromptUseCase(db_session)
        await use_case.add_dynamic_prompt(
            server_name="llm-server",
            prompt_key="dup_key",
            template="Hello {{name}}",
        )
        with pytest.raises(ConflictError, match="already exists"):
            await use_case.add_dynamic_prompt(
                server_name="llm-server",
                prompt_key="dup_key",
                template="Other {{x}}",
            )

    async def test_empty_prompt_key_validation(self, db_session: AsyncSession):
        """空 prompt_key 应抛出 ValidationError"""
        use_case = MCPDynamicPromptUseCase(db_session)
        with pytest.raises(ValidationError, match="prompt_key"):
            await use_case.add_dynamic_prompt(
                server_name="llm-server",
                prompt_key="   ",
                template="x",
            )

    async def test_empty_template_validation(self, db_session: AsyncSession):
        """空 template 应抛出 ValidationError"""
        use_case = MCPDynamicPromptUseCase(db_session)
        with pytest.raises(ValidationError, match="template"):
            await use_case.add_dynamic_prompt(
                server_name="llm-server",
                prompt_key="key",
                template="   ",
            )

    async def test_update_dynamic_prompt(self, db_session: AsyncSession):
        """更新后 list 含更新内容"""
        use_case = MCPDynamicPromptUseCase(db_session)
        await use_case.add_dynamic_prompt(
            server_name="llm-server",
            prompt_key="to_update",
            template="Old",
            title="Old Title",
        )
        record = await use_case.update_dynamic_prompt(
            "llm-server",
            "to_update",
            template="New template",
            title="New Title",
        )
        assert record["template"] == "New template"
        assert record["title"] == "New Title"

        listed = await use_case.list_dynamic_prompts("llm-server")
        one = next((p for p in listed if p["prompt_key"] == "to_update"), None)
        assert one is not None
        assert one["template"] == "New template"
        assert one["title"] == "New Title"

    async def test_update_not_found(self, db_session: AsyncSession):
        """更新不存在的 prompt_key 应抛出 NotFoundError"""
        use_case = MCPDynamicPromptUseCase(db_session)
        with pytest.raises(NotFoundError, match="Dynamic prompt"):
            await use_case.update_dynamic_prompt(
                "llm-server",
                "nonexistent",
                template="x",
            )

    async def test_remove_and_list(self, db_session: AsyncSession):
        """删除后 list 不再包含该记录"""
        use_case = MCPDynamicPromptUseCase(db_session)
        await use_case.add_dynamic_prompt(
            server_name="llm-server",
            prompt_key="to_remove",
            template="Remove me",
        )
        listed_before = await use_case.list_dynamic_prompts("llm-server")
        assert any(p["prompt_key"] == "to_remove" for p in listed_before)

        await use_case.remove_dynamic_prompt("llm-server", "to_remove")

        listed_after = await use_case.list_dynamic_prompts("llm-server")
        assert not any(p["prompt_key"] == "to_remove" for p in listed_after)

    async def test_remove_not_found(self, db_session: AsyncSession):
        """删除不存在的 prompt_key 应抛出 NotFoundError"""
        use_case = MCPDynamicPromptUseCase(db_session)
        with pytest.raises(NotFoundError, match="Dynamic prompt"):
            await use_case.remove_dynamic_prompt("llm-server", "nonexistent_key")
