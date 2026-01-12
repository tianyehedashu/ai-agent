"""
Memory Manager 单元测试

测试记忆提取、存储和检索功能
"""

from unittest.mock import AsyncMock

import pytest

from core.memory.manager import MemoryManager
from tests.mocks.llm_mock import LLMMockBuilder


class TestMemoryManager:
    """记忆管理器测试"""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM Gateway"""
        return LLMMockBuilder().with_text_response(
            '[{"content": "User likes Python", "type": "preference", "importance": 8}]'
        ).build()

    @pytest.fixture
    def mock_vector_store(self):
        """Mock 向量存储"""
        store = AsyncMock()
        store.add.return_value = None
        store.search.return_value = []
        return store

    @pytest.fixture
    def memory_manager(self, mock_llm, mock_vector_store):
        """创建记忆管理器"""
        return MemoryManager(llm=mock_llm, vector_store=mock_vector_store)

    @pytest.mark.asyncio
    async def test_extract_memories_from_conversation(self, memory_manager, mock_llm):
        """测试: 从对话中提取记忆"""
        # Arrange
        conversation = [
            {"role": "user", "content": "I like Python programming"},
            {"role": "assistant", "content": "That's great!"},
        ]

        # Act
        memories = await memory_manager.extract_memories(
            session_id="test-session",
            user_id="test-user",
            conversation=conversation,
        )

        # Assert
        assert isinstance(memories, list)
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_memories_parses_json(self, memory_manager):
        """测试: 解析 JSON 格式的记忆"""
        # Arrange
        json_response = '[{"content": "User prefers dark mode", "type": "preference", "importance": 7}]'
        mock_llm = LLMMockBuilder().with_text_response(json_response).build()
        memory_manager.llm = mock_llm

        conversation = [{"role": "user", "content": "I prefer dark mode"}]

        # Act
        memories = await memory_manager.extract_memories(
            session_id="test-session",
            user_id="test-user",
            conversation=conversation,
        )

        # Assert
        assert len(memories) > 0
        assert memories[0].content == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_extract_memories_handles_empty_response(self, memory_manager):
        """测试: 处理空响应"""
        # Arrange
        mock_llm = LLMMockBuilder().with_text_response("[]").build()
        memory_manager.llm = mock_llm

        conversation = [{"role": "user", "content": "Hello"}]

        # Act
        memories = await memory_manager.extract_memories(
            session_id="test-session",
            user_id="test-user",
            conversation=conversation,
        )

        # Assert
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_extract_memories_handles_invalid_json(self, memory_manager):
        """测试: 处理无效 JSON"""
        # Arrange
        mock_llm = LLMMockBuilder().with_text_response("Invalid JSON").build()
        memory_manager.llm = mock_llm

        conversation = [{"role": "user", "content": "Test"}]

        # Act
        memories = await memory_manager.extract_memories(
            session_id="test-session",
            user_id="test-user",
            conversation=conversation,
        )

        # Assert
        # 应该返回空列表或处理错误
        assert isinstance(memories, list)

    def test_format_conversation(self, memory_manager):
        """测试: 格式化对话"""
        # Arrange
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        # Act
        formatted = memory_manager._format_conversation(conversation)

        # Assert
        assert isinstance(formatted, str)
        assert "Hello" in formatted
        assert "Hi there" in formatted
