"""
Checkpoint Service unit tests.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.domain.types import (
    AgentState,
    Checkpoint,
    Message,
    MessageRole,
)
from exceptions import CheckpointError


@pytest.mark.unit
class TestCheckpointService:
    """Checkpoint Service tests."""

    @pytest.fixture
    def mock_cache(self):
        """Mock CheckpointCache"""
        cache = AsyncMock()
        cache.save_checkpoint = AsyncMock()
        cache.get_checkpoint = AsyncMock()
        cache.add_to_session_index = AsyncMock()
        cache.get_session_checkpoints = AsyncMock(return_value=[])
        return cache

    @pytest.fixture
    def service(self, db_session, mock_cache):
        """Create service instance."""
        # Mock CheckpointCache to return our mock instance
        # Also mock get_redis to avoid Redis initialization errors
        mock_redis = AsyncMock()
        with (
            patch(
                "domains.agent.application.checkpoint_service.CheckpointCache",
                return_value=mock_cache,
            ),
            patch(
                "domains.agent.infrastructure.memory.checkpoint_cache.get_redis",
                return_value=mock_redis,
            ),
            patch(
                "libs.db.redis.get_redis",
                return_value=mock_redis,
            ),
        ):
            return CheckpointService(db_session)

    @pytest.fixture
    def sample_state(self):
        """Sample Agent state."""
        return AgentState(
            session_id=str(uuid.uuid4()),
            messages=[
                Message(
                    role=MessageRole.USER,
                    content="Hello",
                )
            ],
            iteration=1,
            total_tokens=10,
        )

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, service, mock_cache, sample_state):
        """Test: Save checkpoint."""
        # Arrange
        session_id = str(uuid.uuid4())

        # Act
        checkpoint_id = await service.save(
            session_id=session_id,
            step=1,
            state=sample_state,
        )

        # Assert
        assert checkpoint_id is not None
        mock_cache.save_checkpoint.assert_called_once()
        mock_cache.add_to_session_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_checkpoint_with_parent(self, service, mock_cache, sample_state):
        """Test: Save checkpoint with parent."""
        # Arrange
        session_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())

        # Act
        checkpoint_id = await service.save(
            session_id=session_id,
            step=2,
            state=sample_state,
            parent_id=parent_id,
        )

        # Assert
        assert checkpoint_id is not None
        # Verify parent_id is included in save.
        call_args = mock_cache.save_checkpoint.call_args
        checkpoint_data = call_args[0][1]
        assert checkpoint_data["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, service, mock_cache, sample_state):
        """Test: Load checkpoint."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=str(uuid.uuid4()),
            step=1,
            state=sample_state,
            created_at=datetime.now(UTC),
            parent_id=None,
        )
        mock_cache.get_checkpoint.return_value = checkpoint.model_dump(mode="json")

        # Act
        state = await service.load(checkpoint_id)

        # Assert
        assert state is not None
        assert len(state.messages) == 1

    @pytest.mark.asyncio
    async def test_load_checkpoint_not_found(self, service, mock_cache):
        """Test: Loading non-existent checkpoint raises exception."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act & Assert
        with pytest.raises(CheckpointError):
            await service.load(checkpoint_id)

    @pytest.mark.asyncio
    async def test_get_checkpoint(self, service, mock_cache, sample_state):
        """Test: Get checkpoint."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=str(uuid.uuid4()),
            step=1,
            state=sample_state,
            created_at=datetime.now(UTC),
        )
        mock_cache.get_checkpoint.return_value = checkpoint.model_dump(mode="json")

        # Act
        found = await service.get(checkpoint_id)

        # Assert
        assert found is not None
        assert found.id == checkpoint_id

    @pytest.mark.asyncio
    async def test_get_checkpoint_not_found(self, service, mock_cache):
        """Test: Get non-existent checkpoint returns None."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act
        found = await service.get(checkpoint_id)

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_or_raise(self, service, mock_cache, sample_state):
        """Test: Get checkpoint, raise exception if not found."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=str(uuid.uuid4()),
            step=1,
            state=sample_state,
            created_at=datetime.now(UTC),
        )
        mock_cache.get_checkpoint.return_value = checkpoint.model_dump(mode="json")

        # Act
        found = await service.get_or_raise(checkpoint_id)

        # Assert
        assert found.id == checkpoint_id

    @pytest.mark.asyncio
    async def test_get_or_raise_not_found(self, service, mock_cache):
        """Test: Get non-existent checkpoint raises exception."""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act & Assert
        with pytest.raises(CheckpointError):
            await service.get_or_raise(checkpoint_id)

    @pytest.mark.asyncio
    async def test_get_latest(self, service, mock_cache, sample_state):
        """Test: Get latest checkpoint."""
        # Arrange
        session_id = str(uuid.uuid4())
        checkpoint_id = str(uuid.uuid4())
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            step=1,
            state=sample_state,
            created_at=datetime.now(UTC),
        )
        mock_cache.get_session_checkpoints.return_value = [checkpoint_id]
        mock_cache.get_checkpoint.return_value = checkpoint.model_dump(mode="json")

        # Act
        latest = await service.get_latest(session_id)

        # Assert
        assert latest is not None
        assert latest.id == checkpoint_id

    @pytest.mark.asyncio
    async def test_get_latest_not_found(self, service, mock_cache):
        """Test: Get latest checkpoint, returns None if not found."""
        # Arrange
        session_id = str(uuid.uuid4())
        mock_cache.get_session_checkpoints.return_value = []

        # Act
        latest = await service.get_latest(session_id)

        # Assert
        assert latest is None

    @pytest.mark.asyncio
    async def test_list_history(self, service, mock_cache, sample_state):
        """Test: List history checkpoints."""
        # Arrange
        session_id = str(uuid.uuid4())
        checkpoint_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        mock_cache.get_session_checkpoints.return_value = checkpoint_ids

        # Mock each checkpoint.
        checkpoints = []
        for cid in checkpoint_ids:
            checkpoint = Checkpoint(
                id=cid,
                session_id=session_id,
                step=1,
                state=sample_state,
                created_at=datetime.now(UTC),
            )
            checkpoints.append(checkpoint.model_dump(mode="json"))

        mock_cache.get_checkpoint.side_effect = checkpoints

        # Act
        history = await service.list_history(session_id, limit=10)

        # Assert
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_diff_checkpoints(self, service, mock_cache):
        """Test: Compare two checkpoints."""
        # Arrange
        checkpoint_id_1 = str(uuid.uuid4())
        checkpoint_id_2 = str(uuid.uuid4())

        state1 = AgentState(
            session_id=str(uuid.uuid4()),
            messages=[Message(role=MessageRole.USER, content="Hello")],
            iteration=1,
            total_tokens=10,
        )
        state2 = AgentState(
            session_id=str(uuid.uuid4()),
            messages=[
                Message(role=MessageRole.USER, content="Hello"),
                Message(role=MessageRole.ASSISTANT, content="Hi"),
            ],
            iteration=2,
            total_tokens=20,
        )

        checkpoint1 = Checkpoint(
            id=checkpoint_id_1,
            session_id=str(uuid.uuid4()),
            step=1,
            state=state1,
            created_at=datetime.now(UTC),
        )
        checkpoint2 = Checkpoint(
            id=checkpoint_id_2,
            session_id=str(uuid.uuid4()),
            step=2,
            state=state2,
            created_at=datetime.now(UTC),
        )

        def get_checkpoint_side_effect(cid):
            if cid == checkpoint_id_1:
                return checkpoint1.model_dump(mode="json")
            if cid == checkpoint_id_2:
                return checkpoint2.model_dump(mode="json")
            return None

        mock_cache.get_checkpoint.side_effect = get_checkpoint_side_effect

        # Act
        diff = await service.diff(checkpoint_id_1, checkpoint_id_2)

        # Assert
        assert diff["messages_added"] == 1
        assert diff["tokens_delta"] == 10
        assert diff["iteration_delta"] == 1
        assert len(diff["new_messages"]) == 1
