"""
Memory Service unit tests.
"""

import uuid

import pytest

from domains.identity.infrastructure.models.user import User
from domains.runtime.application.memory_service import MemoryService
from exceptions import NotFoundError


@pytest.mark.unit
class TestMemoryService:
    """Memory Service tests."""

    async def _create_test_user(self, db_session) -> User:
        """Helper function to create test user."""
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_create_memory(self, db_session):
        """Test: Create memory."""
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
        """Test: Create memory with metadata."""
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
        """Test: Get memory by ID."""
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
        """Test: Get non-existent memory."""
        # Arrange
        service = MemoryService(db_session)

        # Act
        found = await service.get_by_id(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, db_session):
        """Test: Get memory by ID, raise exception if not found."""
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
        """Test: Get non-existent memory raises exception."""
        # Arrange
        service = MemoryService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.get_by_id_or_raise(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session):
        """Test: Get user's memory list."""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # Create multiple memories.
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
        """Test: Filter memories by type."""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # Create memories of different types.
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
        """Test: Delete memory."""
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
        """Test: Search memory."""
        # Arrange
        user = await self._create_test_user(db_session)
        service = MemoryService(db_session)
        user_id = str(user.id)

        # Create memories.
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
        """Test: Search memory by type."""
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
        """Test: Import knowledge."""
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
        assert len(memories) > 1  # Should be chunked into multiple memories.

    @pytest.mark.asyncio
    async def test_chunk_text(self, db_session):
        """Test: Text chunking functionality."""
        # Arrange
        service = MemoryService(db_session)
        text = "word1 word2 word3 word4 word5"

        # Act
        chunks = service._chunk_text(text, chunk_size=10)

        # Assert
        assert len(chunks) > 1
        assert all(len(chunk) <= 10 for chunk in chunks)
