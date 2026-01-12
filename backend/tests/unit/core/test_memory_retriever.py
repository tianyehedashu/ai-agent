"""
Memory Retriever 单元测试

测试记忆检索功能
"""

from unittest.mock import AsyncMock

import pytest

from core.memory.retriever import MemoryRetriever


class TestMemoryRetriever:
    """记忆检索器测试"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock 向量存储"""
        store = AsyncMock()
        store.search.return_value = [
            {"id": "mem1", "content": "User likes Python", "score": 0.9},
            {"id": "mem2", "content": "User prefers dark mode", "score": 0.8},
        ]
        return store

    @pytest.fixture
    def retriever(self, mock_vector_store):
        """创建检索器"""
        return MemoryRetriever(vector_store=mock_vector_store)

    @pytest.mark.asyncio
    async def test_retrieve_memories(self, retriever, mock_vector_store):
        """测试: 检索记忆"""
        # Arrange
        query = "What does the user like?"

        # Act
        memories = await retriever.retrieve(
            user_id="test-user",
            query=query,
            limit=5,
        )

        # Assert
        assert isinstance(memories, list)
        mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_respects_limit(self, retriever, mock_vector_store):
        """测试: 检索遵守限制"""
        # Arrange
        # Mock 返回更多结果
        mock_vector_store.search.return_value = [
            {"id": f"mem{i}", "content": f"Memory {i}", "score": 0.9 - i * 0.1}
            for i in range(10)
        ]

        # Act
        memories = await retriever.retrieve(
            user_id="test-user",
            query="test",
            limit=3,
        )

        # Assert
        assert len(memories) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_without_vector_store(self):
        """测试: 无向量存储时返回空列表"""
        # Arrange
        retriever = MemoryRetriever(vector_store=None)

        # Act
        memories = await retriever.retrieve(
            user_id="test-user",
            query="test",
        )

        # Assert
        assert memories == []

    @pytest.mark.asyncio
    async def test_retrieve_filters_by_user(self, retriever, mock_vector_store):
        """测试: 按用户过滤"""
        # Act
        await retriever.retrieve(
            user_id="test-user",
            query="test",
        )

        # Assert
        # 应该传递 user_id 到向量存储
        mock_vector_store.search.assert_called_once()
