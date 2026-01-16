"""
Checkpoint Service 单元测试
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from core.types import AgentState, Checkpoint, Message, MessageRole
from exceptions import CheckpointError
from services.checkpoint import CheckpointService


@pytest.mark.unit
class TestCheckpointService:
    """Checkpoint Service 测试"""

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
        """创建服务实例"""
        with patch("services.checkpoint.CheckpointCache", return_value=mock_cache):
            return CheckpointService(db_session)

    @pytest.fixture
    def sample_state(self):
        """示例 Agent 状态"""
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
        """测试: 保存检查点"""
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
        """测试: 保存带父检查点的检查点"""
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
        # 验证保存时包含了 parent_id
        call_args = mock_cache.save_checkpoint.call_args
        checkpoint_data = call_args[0][1]
        assert checkpoint_data["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, service, mock_cache, sample_state):
        """测试: 加载检查点"""
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
        """测试: 加载不存在的检查点抛出异常"""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act & Assert
        with pytest.raises(CheckpointError):
            await service.load(checkpoint_id)

    @pytest.mark.asyncio
    async def test_get_checkpoint(self, service, mock_cache, sample_state):
        """测试: 获取检查点"""
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
        """测试: 获取不存在的检查点返回 None"""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act
        found = await service.get(checkpoint_id)

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_or_raise(self, service, mock_cache, sample_state):
        """测试: 获取检查点，不存在则抛出异常"""
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
        """测试: 获取不存在的检查点抛出异常"""
        # Arrange
        checkpoint_id = str(uuid.uuid4())
        mock_cache.get_checkpoint.return_value = None

        # Act & Assert
        with pytest.raises(CheckpointError):
            await service.get_or_raise(checkpoint_id)

    @pytest.mark.asyncio
    async def test_get_latest(self, service, mock_cache, sample_state):
        """测试: 获取最新检查点"""
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
        """测试: 获取最新检查点，不存在返回 None"""
        # Arrange
        session_id = str(uuid.uuid4())
        mock_cache.get_session_checkpoints.return_value = []

        # Act
        latest = await service.get_latest(session_id)

        # Assert
        assert latest is None

    @pytest.mark.asyncio
    async def test_list_history(self, service, mock_cache, sample_state):
        """测试: 列出历史检查点"""
        # Arrange
        session_id = str(uuid.uuid4())
        checkpoint_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        mock_cache.get_session_checkpoints.return_value = checkpoint_ids

        # Mock 每个检查点
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
        """测试: 对比两个检查点"""
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
