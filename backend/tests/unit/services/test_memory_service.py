"""
Memory Service 单元测试
"""

import uuid

import pytest

from exceptions import NotFoundError
from models.user import User
from services.memory import MemoryService


@pytest.mark.unit
class TestMemoryService:
    """Memory Service 测试"""

    async def _create_test_user(self, db_session) -> User:
        """创建测试用户辅助函数"""
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            password_hash="hashed_password",
            name="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_create_memory(self, db_session):
        """测试: 创建记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # Act
        memory = await service.create(
            user_id=user_id,
            type="fact",
            content="User likes Python",
            importance=0.8,
        )

        # Assert
        assert memory.id is not None
        assert memory.type == "fact"
        assert memory.content == "User likes Python"
        assert memory.importance == 0.8
        assert memory.user_id == uuid.UUID(user_id)

    @pytest.mark.asyncio
    async def test_create_memory_with_metadata(self, db_session):
        """测试: 创建带元数据的记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)
        metadata = {"source": "conversation", "session_id": "123"}

        # Act
        memory = await service.create(
            user_id=user_id,
            type="preference",
            content="User prefers dark mode",
            metadata=metadata,
        )

        # Assert
        assert memory.extra_data == metadata

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """测试: 通过 ID 获取记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)
        memory = await service.create(
            user_id=user_id,
            type="fact",
            content="Test content",
        )

        # Act
        found = await service.get_by_id(str(memory.id))

        # Assert
        assert found is not None
        assert found.id == memory.id
        assert found.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session):
        """测试: 获取不存在的记忆"""
        # Arrange
        service = MemoryService(db_session)

        # Act
        found = await service.get_by_id(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, db_session):
        """测试: 通过 ID 获取记忆，不存在则抛出异常"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)
        memory = await service.create(
            user_id=user_id,
            type="fact",
            content="Test content",
        )

        # Act
        found = await service.get_by_id_or_raise(str(memory.id))

        # Assert
        assert found.id == memory.id

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_found(self, db_session):
        """测试: 获取不存在的记忆抛出异常"""
        # Arrange
        service = MemoryService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.get_by_id_or_raise(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session):
        """测试: 获取用户的记忆列表"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # 创建多个记忆
        await service.create(
            user_id=user_id,
            type="fact",
            content="Memory 1",
        )
        await service.create(
            user_id=user_id,
            type="preference",
            content="Memory 2",
        )

        # Act
        memories = await service.list_by_user(user_id)

        # Assert
        assert len(memories) >= 2

    @pytest.mark.asyncio
    async def test_list_by_user_with_type_filter(self, db_session):
        """测试: 按类型筛选记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # 创建不同类型的记忆
        await service.create(
            user_id=user_id,
            type="fact",
            content="Fact memory",
        )
        await service.create(
            user_id=user_id,
            type="preference",
            content="Preference memory",
        )

        # Act
        facts = await service.list_by_user(user_id, type_filter="fact")

        # Assert
        assert len(facts) >= 1
        assert all(m.type == "fact" for m in facts)

    @pytest.mark.asyncio
    async def test_delete_memory(self, db_session):
        """测试: 删除记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)
        memory = await service.create(
            user_id=user_id,
            type="fact",
            content="To be deleted",
        )

        # Act
        await service.delete(str(memory.id))

        # Assert
        found = await service.get_by_id(str(memory.id))
        assert found is None

    @pytest.mark.asyncio
    async def test_search_memory(self, db_session):
        """测试: 搜索记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # 创建记忆
        await service.create(
            user_id=user_id,
            type="fact",
            content="User likes Python programming",
            importance=0.9,
        )
        await service.create(
            user_id=user_id,
            type="fact",
            content="User prefers JavaScript",
            importance=0.5,
        )

        # Act
        results = await service.search(user_id, "Python")

        # Assert
        assert len(results) >= 1
        assert any("Python" in m.content for m in results)

    @pytest.mark.asyncio
    async def test_search_memory_with_type_filter(self, db_session):
        """测试: 按类型搜索记忆"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        await service.create(
            user_id=user_id,
            type="fact",
            content="Python fact",
        )
        await service.create(
            user_id=user_id,
            type="preference",
            content="Python preference",
        )

        # Act
        results = await service.search(user_id, "Python", type_filter="fact")

        # Assert
        assert len(results) >= 1
        assert all(m.type == "fact" for m in results)

    @pytest.mark.asyncio
    async def test_import_knowledge(self, db_session):
        """测试: 导入知识"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)
        content = "This is a long text that will be chunked into multiple memories. " * 10

        # Act
        task_id = await service.import_knowledge(
            user_id=user_id,
            content=content,
            source="document",
            chunk_size=50,
        )

        # Assert
        assert task_id is not None
        memories = await service.list_by_user(user_id)
        assert len(memories) > 1  # 应该被分块成多个记忆

    @pytest.mark.asyncio
    async def test_chunk_text(self, db_session):
        """测试: 文本分块功能"""
        # Arrange
        service = MemoryService(db_session)
        text = "word1 word2 word3 word4 word5"

        # Act
        chunks = service._chunk_text(text, chunk_size=10)

        # Assert
        assert len(chunks) > 1
        assert all(len(chunk) <= 10 for chunk in chunks)
