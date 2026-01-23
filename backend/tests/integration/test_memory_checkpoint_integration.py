"""
全流程功能测试：记忆和检查点系统集成（基于 LangGraph）

测试范围：
1. LongTermMemoryStore - 长期记忆存储和检索
2. LangGraphCheckpointer - 检查点保存和恢复（自动管理对话历史）
3. LangGraphAgentEngine - 完整的 Agent 执行流程，集成记忆和检查点

注意：对话历史由 LangGraph checkpointer 自动管理，无需额外的 ConversationMemory
"""

import uuid

import pytest

from bootstrap.config import settings
from domains.runtime.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from shared.infrastructure.llm.gateway import LLMGateway
from domains.runtime.infrastructure.memory.langgraph_store import LongTermMemoryStore
from shared.infrastructure.db.vector import get_vector_store


@pytest.fixture
async def llm_gateway():
    """创建 LLM Gateway 实例"""
    return LLMGateway(config=settings)


@pytest.fixture
async def vector_store():
    """创建向量存储实例"""
    return get_vector_store()


@pytest.fixture
async def memory_store(llm_gateway, vector_store):
    """创建长期记忆存储实例"""
    store = LongTermMemoryStore(
        llm_gateway=llm_gateway,
        vector_store=vector_store,
    )
    await store.setup()
    return store


@pytest.fixture
async def checkpointer():
    """创建检查点管理器实例"""
    checkpointer = LangGraphCheckpointer(storage_type="postgres")
    await checkpointer.setup()
    return checkpointer


@pytest.mark.asyncio
@pytest.mark.integration
class TestLongTermMemoryStore:
    """测试长期记忆存储（按 session_id 隔离）"""

    async def test_store_and_retrieve_memory(
        self,
        memory_store: LongTermMemoryStore,
    ):
        """测试存储和检索记忆"""
        session_id = str(uuid.uuid4())
        memory_type = "preference"
        content = "我喜欢使用 Python 编程，偏好函数式编程风格"

        # 存储记忆（按 session_id 隔离）
        memory_id = await memory_store.put(
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            importance=8.0,
            metadata={"source": "test"},
        )

        assert memory_id is not None

        # 检索记忆
        memories = await memory_store.search(
            session_id=session_id,
            query="编程语言偏好",
            limit=10,
        )

        assert len(memories) > 0
        assert memories[0]["content"] == content
        assert memories[0]["type"] == memory_type
        assert memories[0]["importance"] == 8.0

    async def test_search_with_type_filter(
        self,
        memory_store: LongTermMemoryStore,
    ):
        """测试按类型过滤搜索"""
        session_id = str(uuid.uuid4())

        # 存储不同类型的记忆
        await memory_store.put(
            session_id=session_id,
            memory_type="preference",
            content="我喜欢喝咖啡",
            importance=7.0,
        )

        await memory_store.put(
            session_id=session_id,
            memory_type="fact",
            content="咖啡因是一种兴奋剂",
            importance=5.0,
        )

        # 只搜索 preference 类型
        preferences = await memory_store.search(
            session_id=session_id,
            query="偏好",
            limit=10,
            memory_type="preference",
        )

        assert len(preferences) > 0
        assert all(m["type"] == "preference" for m in preferences)

    async def test_delete_memory(
        self,
        memory_store: LongTermMemoryStore,
    ):
        """测试删除记忆"""
        session_id = str(uuid.uuid4())
        memory_type = "fact"
        content = "测试记忆，将被删除"

        # 存储记忆
        memory_id = await memory_store.put(
            session_id=session_id,
            memory_type=memory_type,
            content=content,
        )

        # 删除记忆
        await memory_store.delete(
            session_id=session_id,
            memory_id=memory_id,
            memory_type=memory_type,
        )

        # 确认已删除
        memories = await memory_store.search(
            session_id=session_id,
            query="测试",
            limit=10,
        )

        # 应该找不到或分数很低
        assert not any(m["id"] == memory_id for m in memories)


@pytest.mark.asyncio
@pytest.mark.integration
class TestLangGraphCheckpointer:
    """测试 LangGraph 检查点管理器"""

    async def test_checkpointer_initialization(
        self,
        checkpointer: LangGraphCheckpointer,
    ):
        """测试检查点管理器初始化"""
        assert checkpointer is not None
        assert checkpointer.checkpointer is not None

    async def test_get_checkpointer(
        self,
        checkpointer: LangGraphCheckpointer,
    ):
        """测试获取原始 Checkpointer 实例"""
        checkpointer_instance = checkpointer.get_checkpointer()
        assert checkpointer_instance is not None

    async def test_get_config(
        self,
        checkpointer: LangGraphCheckpointer,
    ):
        """测试获取 LangGraph 配置"""
        session_id = str(uuid.uuid4())
        config = checkpointer.get_config(session_id)

        assert "configurable" in config
        assert config["configurable"]["thread_id"] == session_id


@pytest.mark.asyncio
@pytest.mark.integration
class TestMemoryCheckpointIntegration:
    """测试记忆和检查点系统集成"""

    async def test_full_workflow(
        self,
        memory_store: LongTermMemoryStore,
        checkpointer: LangGraphCheckpointer,
    ):
        """测试完整工作流程"""
        session_id = str(uuid.uuid4())

        # 1. 存储会话内长程记忆（按 session_id 隔离）
        memory_id = await memory_store.put(
            session_id=session_id,
            memory_type="preference",
            content="用户喜欢使用简洁的命令行界面",
            importance=7.0,
        )
        assert memory_id is not None

        # 2. 检索会话内记忆
        memories = await memory_store.search(
            session_id=session_id,
            query="用户偏好",
            limit=5,
        )
        assert len(memories) > 0

        # 3. 测试检查点配置（对话历史由 checkpointer 自动管理）
        config = checkpointer.get_config(session_id)
        assert config["configurable"]["thread_id"] == session_id

        # 验证所有组件正常工作
        assert memory_store is not None
        assert checkpointer is not None

    async def test_memory_extraction_workflow(
        self,
        memory_store: LongTermMemoryStore,
        llm_gateway: LLMGateway,
    ):
        """测试记忆提取工作流程"""
        session_id = str(uuid.uuid4())

        # 简化测试，直接存储会话内记忆
        await memory_store.put(
            session_id=session_id,
            memory_type="fact",
            content="用户姓名：李四，职业：软件工程师",
            importance=9.0,
        )

        await memory_store.put(
            session_id=session_id,
            memory_type="preference",
            content="用户偏好：Python 和 TypeScript 编程语言",
            importance=8.0,
        )

        # 检索相关记忆
        memories = await memory_store.search(
            session_id=session_id,
            query="用户信息",
            limit=10,
        )

        assert len(memories) >= 2
        assert any("李四" in m["content"] for m in memories)
        assert any("Python" in m["content"] for m in memories)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
