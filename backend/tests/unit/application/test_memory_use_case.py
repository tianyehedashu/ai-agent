"""
Memory Service unit tests.
"""

from contextlib import asynccontextmanager
import uuid

import pytest

from domains.agent.application.memory_service import MemoryService
from domains.identity.infrastructure.models.user import User
from libs.exceptions import NotFoundError
from libs.iam.permission_context import clear_permission_context, set_permission_context
from tests.helpers.permission_context import permission_context_for_user


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

    @asynccontextmanager
    async def _user_context(self, db_session):
        user = await self._create_test_user(db_session)
        set_permission_context(
            await permission_context_for_user(db_session, user_id=user.id)
        )
        try:
            yield user
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_create_memory(self, db_session):
        """Test: Create memory."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            memory = await service.create(
                user_id=user_id,
                type="fact",
                content="User likes Python",
                importance=5,
            )
            assert memory.id is not None
            assert memory.type == "fact"
            assert memory.content == "User likes Python"
            assert memory.importance == 5
            assert memory.user_id == uuid.UUID(user_id)
            assert memory.tenant_id is not None

    @pytest.mark.asyncio
    async def test_create_memory_with_metadata(self, db_session):
        """Test: Create memory with metadata."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            metadata = {"source": "conversation", "session_id": "123"}
            memory = await service.create(
                user_id=str(user.id),
                type="preference",
                content="User prefers dark mode",
                metadata=metadata,
            )
            assert memory.extra_data == metadata

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """Test: Get memory by ID."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            memory = await service.create(
                user_id=user_id,
                type="fact",
                content="Test content",
            )
            found = await service.get_by_id(str(memory.id))
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
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            memory = await service.create(
                user_id=str(user.id),
                type="fact",
                content="Test content",
            )
            found = await service.get_by_id_or_raise(str(memory.id))
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
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            await service.create(user_id=user_id, type="fact", content="Memory 1")
            await service.create(user_id=user_id, type="preference", content="Memory 2")
            memories = await service.list_by_user(user_id)
            assert len(memories) >= 2

    @pytest.mark.asyncio
    async def test_list_by_user_with_type_filter(self, db_session):
        """Test: Filter memories by type."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            await service.create(user_id=user_id, type="fact", content="Fact memory")
            await service.create(user_id=user_id, type="preference", content="Preference memory")
            facts = await service.list_by_user(user_id, type_filter="fact")
            assert len(facts) >= 1
            assert all(m.type == "fact" for m in facts)

    @pytest.mark.asyncio
    async def test_delete_memory(self, db_session):
        """Test: Delete memory."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            memory = await service.create(
                user_id=user_id,
                type="fact",
                content="To be deleted",
            )
            await service.delete(str(memory.id))
            assert await service.get_by_id(str(memory.id)) is None

    @pytest.mark.asyncio
    async def test_search_memory(self, db_session):
        """Test: Search memory."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
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
            results = await service.search(user_id, "Python")
            assert len(results) >= 1
            assert any("Python" in m.content for m in results)

    @pytest.mark.asyncio
    async def test_search_memory_with_type_filter(self, db_session):
        """Test: Search memory by type."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            await service.create(user_id=user_id, type="fact", content="Python fact")
            await service.create(user_id=user_id, type="preference", content="Python preference")
            results = await service.search(user_id, "Python", type_filter="fact")
            assert len(results) >= 1
            assert all(m.type == "fact" for m in results)

    @pytest.mark.asyncio
    async def test_import_knowledge(self, db_session):
        """Test: Import knowledge."""
        async with self._user_context(db_session) as user:
            service = MemoryService(db_session)
            user_id = str(user.id)
            content = "This is a long text that will be chunked into multiple memories. " * 10
            task_id = await service.import_knowledge(
                user_id=user_id,
                content=content,
                source="document",
                chunk_size=50,
            )
            assert task_id is not None
            assert len(await service.list_by_user(user_id)) > 1

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
