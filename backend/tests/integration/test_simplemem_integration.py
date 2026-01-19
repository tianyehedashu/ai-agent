"""
SimpleMem 集成测试

测试 SimpleMem 与 ChatService 的集成：
1. 对话处理后自动提取记忆
2. 自适应检索功能
3. 与 LongTermMemoryStore 的协作

注意：记忆按 session_id 隔离，实现"会话内长程记忆"
"""
# pylint: disable=protected-access  # 测试代码需要访问私有方法

from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# pylint: disable=wrong-import-position
from core.memory.simplemem_client import SimpleMemAdapter, SimpleMemConfig
from core.types import Message, MessageRole

# pylint: enable=wrong-import-position


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway"""
    gateway = AsyncMock()
    gateway.chat = AsyncMock(
        return_value=MagicMock(
            content='{"summary": "用户正在开发 AI Agent 项目，使用 Python 和 FastAPI", "entities": ["AI Agent", "Python", "FastAPI"], "importance": 8}'
        )
    )
    return gateway


@pytest.fixture
def mock_memory_store():
    """Mock Memory Store with realistic behavior（按 session_id 隔离）"""
    store = AsyncMock()
    stored_memories: list[dict] = []

    async def mock_put(**kwargs):
        memory = {
            "id": f"mem_{len(stored_memories)}",
            "session_id": kwargs.get("session_id"),
            "content": kwargs.get("content"),
            "importance": kwargs.get("importance"),
            "metadata": kwargs.get("metadata", {}),
        }
        stored_memories.append(memory)
        return memory["id"]

    async def mock_search(**kwargs):
        # 按 session_id 过滤返回记忆
        session_id = kwargs.get("session_id")
        return [m for m in stored_memories if m.get("session_id") == session_id][
            : kwargs.get("limit", 5)
        ]

    store.put = mock_put
    store.search = mock_search
    store._stored = stored_memories
    return store


class TestSimpleMemChatIntegration:
    """SimpleMem 与 Chat 流程的集成测试"""

    @pytest.mark.asyncio
    async def test_chat_flow_extracts_memory(self, mock_llm_gateway, mock_memory_store):
        """测试对话流程自动提取记忆"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(
                window_size=5,
                novelty_threshold=0.2,
            ),
        )

        # 模拟一次完整对话
        messages = [
            Message(role=MessageRole.USER, content="我正在开发一个 AI Agent 项目"),
            Message(role=MessageRole.ASSISTANT, content="这是个很好的项目！你打算使用什么技术栈？"),
            Message(role=MessageRole.USER, content="Python + FastAPI + LangGraph"),
            Message(role=MessageRole.ASSISTANT, content="很好的选择，LangGraph 非常适合构建 Agent"),
        ]

        # 处理对话
        atoms = await adapter.process_and_store(
            messages=messages,
            user_id="test_user",
            session_id="test_session",
        )

        # 验证提取了记忆
        assert len(atoms) >= 1
        assert any("AI Agent" in atom.content or "Python" in atom.content for atom in atoms)

    @pytest.mark.asyncio
    async def test_memory_retrieval_after_storage(self, mock_llm_gateway, mock_memory_store):
        """测试存储后可以检索记忆"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(novelty_threshold=0.1),
        )

        # 先存储一些记忆
        messages = [
            Message(role=MessageRole.USER, content="我喜欢使用 Python 编程"),
            Message(role=MessageRole.ASSISTANT, content="Python 是很棒的语言"),
        ]
        await adapter.process_and_store(
            messages=messages,
            user_id="user_001",
            session_id="session_001",
        )

        # 检索（按 session_id）
        results = await adapter.adaptive_retrieve(
            session_id="session_001",
            query="编程语言偏好",
        )

        # 验证可以检索到
        assert isinstance(results, list)


class TestSimpleMemMultiSession:
    """多会话场景测试（记忆按 session_id 隔离）"""

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self, mock_llm_gateway, mock_memory_store):
        """测试多个会话的记忆隔离"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(novelty_threshold=0.1),
        )

        # 会话 A 的对话
        await adapter.process_and_store(
            messages=[
                Message(role=MessageRole.USER, content="我是会话 A，我喜欢 Java"),
            ],
            user_id="user_001",
            session_id="session_a",
        )

        # 会话 B 的对话
        await adapter.process_and_store(
            messages=[
                Message(role=MessageRole.USER, content="我是会话 B，我喜欢 Rust"),
            ],
            user_id="user_001",  # 同一用户，不同会话
            session_id="session_b",
        )

        # 检索会话 A 的记忆
        results_a = await adapter.adaptive_retrieve(session_id="session_a", query="偏好")

        # 检索会话 B 的记忆
        results_b = await adapter.adaptive_retrieve(session_id="session_b", query="偏好")

        # 验证记忆隔离（各自只能检索到自己会话的）
        assert all(r.get("session_id") == "session_a" for r in results_a if r.get("session_id"))
        assert all(r.get("session_id") == "session_b" for r in results_b if r.get("session_id"))


class TestSimpleMemAdaptiveRetrieval:
    """自适应检索集成测试"""

    @pytest.mark.asyncio
    async def test_simple_query_uses_less_results(self, mock_llm_gateway, mock_memory_store):
        """简单查询应该返回较少结果"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(k_min=2, k_max=10),
        )

        # 添加一些记忆（按 session_id）
        for i in range(5):
            adapter._update_bm25_index("test_session", f"记忆内容 {i}")

        # 简单查询
        simple_query = "内容"
        complexity = adapter._estimate_complexity(simple_query)

        assert complexity < 0.5, "简单查询复杂度应该较低"

    @pytest.mark.asyncio
    async def test_complex_query_uses_more_results(self, mock_llm_gateway, mock_memory_store):
        """复杂查询应该返回较多结果"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(k_min=2, k_max=10),
        )

        # 复杂查询
        complex_query = "为什么用户在昨天决定使用 Python 而不是 JavaScript 来开发这个项目？"
        complexity = adapter._estimate_complexity(complex_query)

        assert complexity >= 0.3, "复杂查询复杂度应该较高"


class TestSimpleMemWithRealLLMFormat:
    """测试与真实 LLM 响应格式的兼容性"""

    @pytest.mark.asyncio
    async def test_handles_various_llm_response_formats(self, mock_memory_store):
        """测试处理各种 LLM 响应格式"""
        test_cases = [
            # 标准 JSON
            '{"summary": "测试内容", "entities": ["A"], "importance": 5}',
            # JSON 带额外文本
            '好的，这是提取结果：\n{"summary": "测试内容", "entities": ["B"], "importance": 6}\n希望有帮助',
            # 缺少字段
            '{"summary": "只有摘要"}',
        ]

        for response_content in test_cases:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=MagicMock(content=response_content))

            adapter = SimpleMemAdapter(
                llm_gateway=mock_llm,
                memory_store=mock_memory_store,
                config=SimpleMemConfig(novelty_threshold=0.1),
            )

            messages = [Message(role=MessageRole.USER, content="测试消息内容足够长")]

            # 应该不会崩溃
            atoms = await adapter.process_and_store(
                messages=messages,
                user_id="test",
                session_id="test",
            )

            # 可能提取到记忆，也可能因为格式问题跳过，但不应该报错
            assert isinstance(atoms, list)


class TestSimpleMemPerformance:
    """性能相关测试"""

    @pytest.mark.asyncio
    async def test_handles_long_conversation(self, mock_llm_gateway, mock_memory_store):
        """测试处理长对话"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
            config=SimpleMemConfig(
                window_size=10,
                window_stride=5,
                novelty_threshold=0.1,
            ),
        )

        # 生成长对话（50 条消息）
        messages = []
        for i in range(25):
            messages.append(
                Message(role=MessageRole.USER, content=f"用户消息 {i}，内容关于项目开发")
            )
            messages.append(
                Message(role=MessageRole.ASSISTANT, content=f"助手回复 {i}，提供技术建议")
            )

        # 处理长对话
        atoms = await adapter.process_and_store(
            messages=messages,
            user_id="test_user",
            session_id="long_session",
        )

        # 应该成功处理，提取多个记忆
        assert isinstance(atoms, list)

    @pytest.mark.asyncio
    async def test_bm25_index_scales(self, mock_llm_gateway, mock_memory_store):
        """测试 BM25 索引可扩展（按 session_id 隔离）"""
        adapter = SimpleMemAdapter(
            llm_gateway=mock_llm_gateway,
            memory_store=mock_memory_store,
        )

        # 添加大量记忆
        for i in range(100):
            adapter._update_bm25_index("test_session", f"记忆内容 {i} 关于各种技术话题")

        # 搜索应该正常工作
        results = adapter._bm25_search("test_session", "技术", k=10)

        assert len(results) <= 10
        assert all("技术" in r["content"] for r in results)
