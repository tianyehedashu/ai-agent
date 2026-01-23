"""
SimpleMem Adapter 测试

测试 SimpleMem 的三个核心阶段：
1. 语义结构化压缩
2. 递归记忆整合
3. 自适应查询检索
"""

from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# 直接导入，避免循环依赖
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domains.agent.domain.types import (
    Message,
    MessageRole,
)
from domains.agent.infrastructure.memory.simplemem_client import (
    MemoryAtom,
    SimpleMemAdapter,
    SimpleMemConfig,
)


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway"""
    gateway = AsyncMock()
    gateway.chat = AsyncMock(
        return_value=MagicMock(
            content='{"summary": "用户喜欢 Python 编程", "entities": ["Python"], "importance": 7}'
        )
    )
    return gateway


@pytest.fixture
def mock_memory_store():
    """Mock Memory Store"""
    store = AsyncMock()
    store.put = AsyncMock(return_value="mem_123")
    store.search = AsyncMock(
        return_value=[
            {"content": "用户喜欢 Python 编程", "importance": 7.0},
            {"content": "用户的项目使用 FastAPI", "importance": 6.0},
        ]
    )
    return store


@pytest.fixture
def adapter(mock_llm_gateway, mock_memory_store):
    """创建 SimpleMem 适配器"""
    return SimpleMemAdapter(
        llm_gateway=mock_llm_gateway,
        memory_store=mock_memory_store,
        config=SimpleMemConfig(
            window_size=5,
            window_stride=3,
            novelty_threshold=0.2,  # 降低阈值便于测试
            k_min=2,
            k_max=10,
        ),
    )


class TestSimpleMemConfig:
    """测试配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = SimpleMemConfig()
        assert config.window_size == 10
        assert config.k_min == 3
        assert config.k_max == 15
        assert config.novelty_threshold == 0.35

    def test_custom_config(self):
        """测试自定义配置"""
        config = SimpleMemConfig(
            window_size=20,
            k_min=5,
            k_max=20,
        )
        assert config.window_size == 20
        assert config.k_min == 5
        assert config.k_max == 20


class TestNoveltyCalculation:
    """测试信息新颖性计算"""

    def test_high_novelty_content(self, adapter):
        """测试高新颖性内容"""
        messages = [
            Message(role=MessageRole.USER, content="我想学习 Python 编程，目标是开发 Web 应用"),
            Message(role=MessageRole.ASSISTANT, content="好的，我推荐你从 FastAPI 框架开始学习"),
        ]
        novelty = adapter._calculate_novelty(messages)
        assert novelty > 0.3, f"Expected high novelty, got {novelty}"

    def test_low_novelty_content(self, adapter):
        """测试低新颖性内容"""
        messages = [
            Message(role=MessageRole.USER, content="好 好 好"),
            Message(role=MessageRole.ASSISTANT, content="好 好"),
        ]
        novelty = adapter._calculate_novelty(messages)
        assert novelty < 0.3, f"Expected low novelty, got {novelty}"

    def test_empty_content(self, adapter):
        """测试空内容"""
        messages = [
            Message(role=MessageRole.USER, content=""),
        ]
        novelty = adapter._calculate_novelty(messages)
        assert novelty == 0.0


class TestComplexityEstimation:
    """测试查询复杂度估算"""

    def test_simple_query(self, adapter):
        """测试简单查询"""
        query = "用户偏好"
        complexity = adapter._estimate_complexity(query)
        assert complexity < 0.5, f"Expected low complexity, got {complexity}"

    def test_complex_query(self, adapter):
        """测试复杂查询"""
        query = (
            "为什么用户在上周决定使用 Python 而不是 JavaScript 来开发这个项目？这是什么原因导致的？"
        )
        complexity = adapter._estimate_complexity(query)
        assert complexity >= 0.4, f"Expected high complexity, got {complexity}"

    def test_query_with_time(self, adapter):
        """测试包含时间的查询"""
        query = "用户昨天说了什么"
        complexity = adapter._estimate_complexity(query)
        assert complexity >= 0.2, "Time expression should increase complexity"

    def test_query_with_entities(self, adapter):
        """测试包含实体的查询"""
        query = "Python FastAPI React 的使用情况"
        complexity = adapter._estimate_complexity(query)
        assert complexity >= 0.2, "Entities should increase complexity"


class TestProcessAndStore:
    """测试对话处理和存储"""

    @pytest.mark.asyncio
    async def test_process_conversation(self, adapter, mock_memory_store):
        """测试处理对话"""
        messages = [
            Message(role=MessageRole.USER, content="我想学习 Python 编程语言"),
            Message(role=MessageRole.ASSISTANT, content="Python 是一门很好的编程语言，适合初学者"),
            Message(role=MessageRole.USER, content="有什么推荐的学习资源吗？"),
            Message(role=MessageRole.ASSISTANT, content="我推荐官方文档和 Real Python 网站"),
        ]

        atoms = await adapter.process_and_store(
            messages=messages,
            user_id="test_user",
            session_id="session_001",
        )

        # 验证提取了记忆
        assert len(atoms) >= 1, "Should extract at least one memory atom"

        # 验证存储被调用
        assert mock_memory_store.put.called, "Memory store should be called"

    @pytest.mark.asyncio
    async def test_process_empty_messages(self, adapter):
        """测试处理空消息"""
        atoms = await adapter.process_and_store(
            messages=[],
            user_id="test_user",
            session_id="session_001",
        )
        assert atoms == []

    @pytest.mark.asyncio
    async def test_atom_structure(self, adapter):
        """测试原子记忆结构"""
        messages = [
            Message(role=MessageRole.USER, content="我的名字是张三，我喜欢编程"),
            Message(role=MessageRole.ASSISTANT, content="你好张三，很高兴认识你"),
        ]

        atoms = await adapter.process_and_store(
            messages=messages,
            user_id="test_user",
            session_id="session_001",
        )

        if atoms:
            atom = atoms[0]
            assert isinstance(atom, MemoryAtom)
            assert atom.id is not None
            assert atom.content is not None
            assert atom.source_session == "session_001"
            assert 1 <= atom.importance <= 10


class TestAdaptiveRetrieve:
    """测试自适应检索（按 session_id 隔离）"""

    @pytest.mark.asyncio
    async def test_simple_query_retrieval(self, adapter, mock_memory_store):
        """测试简单查询检索"""
        _results = await adapter.adaptive_retrieve(
            session_id="test_session",
            query="偏好",
        )

        # 简单查询应该使用较小的 k
        assert mock_memory_store.search.called
        call_args = mock_memory_store.search.call_args
        assert call_args.kwargs.get("limit", 10) <= adapter.config.k_max

    @pytest.mark.asyncio
    async def test_complex_query_retrieval(self, adapter, mock_memory_store):
        """测试复杂查询检索"""
        _results = await adapter.adaptive_retrieve(
            session_id="test_session",
            query="为什么用户在上周决定使用 Python 而不是 JavaScript？",
        )

        assert mock_memory_store.search.called

    @pytest.mark.asyncio
    async def test_explicit_k(self, adapter, mock_memory_store):
        """测试显式指定 k"""
        _results = await adapter.adaptive_retrieve(
            session_id="test_session",
            query="测试",
            k=7,
        )

        call_args = mock_memory_store.search.call_args
        assert call_args.kwargs.get("limit") == 7


class TestBM25Index:
    """测试 BM25 索引（按 session_id 隔离）"""

    def test_update_index(self, adapter):
        """测试更新索引"""
        adapter._update_bm25_index("session1", "Python 编程语言")
        adapter._update_bm25_index("session1", "FastAPI Web 框架")

        assert "session1" in adapter._bm25_corpus
        assert len(adapter._bm25_corpus["session1"]) == 2
        assert "session1" in adapter._bm25_index

    def test_bm25_search(self, adapter):
        """测试 BM25 搜索"""
        adapter._update_bm25_index("session1", "Python 是一门编程语言")
        adapter._update_bm25_index("session1", "FastAPI 是 Python Web 框架")
        adapter._update_bm25_index("session1", "React 是前端框架")

        results = adapter._bm25_search("session1", "Python 框架", k=2)

        assert len(results) <= 2
        # Python 相关的应该排在前面
        if results:
            assert "Python" in results[0]["content"]

    def test_bm25_search_empty_index(self, adapter):
        """测试空索引搜索"""
        results = adapter._bm25_search("nonexistent_session", "query", k=5)
        assert results == []


class TestRRFFusion:
    """测试 RRF 融合"""

    def test_fusion_with_overlap(self, adapter):
        """测试有重叠的融合"""
        semantic = [
            {"content": "Python 编程", "score": 0.9},
            {"content": "FastAPI 框架", "score": 0.8},
        ]
        lexical = [
            {"content": "Python 编程", "bm25_score": 10.0},
            {"content": "React 前端", "bm25_score": 8.0},
        ]

        merged = adapter._reciprocal_rank_fusion(semantic, lexical, k=3)

        assert len(merged) == 3
        # Python 编程应该排第一（两个列表都有）
        assert merged[0]["content"] == "Python 编程"

    def test_fusion_no_overlap(self, adapter):
        """测试无重叠的融合"""
        semantic = [{"content": "A", "score": 0.9}]
        lexical = [{"content": "B", "bm25_score": 10.0}]

        merged = adapter._reciprocal_rank_fusion(semantic, lexical, k=2)

        assert len(merged) == 2
        contents = {m["content"] for m in merged}
        assert contents == {"A", "B"}


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, adapter, mock_memory_store):
        """测试完整工作流：存储 -> 检索（按 session_id 隔离）"""
        # 1. 处理对话
        messages = [
            Message(role=MessageRole.USER, content="我正在开发一个 AI Agent 项目"),
            Message(role=MessageRole.ASSISTANT, content="这是一个很有趣的项目，使用什么技术栈？"),
            Message(role=MessageRole.USER, content="Python + FastAPI + LangGraph"),
            Message(
                role=MessageRole.ASSISTANT, content="很好的选择，LangGraph 适合构建复杂的 Agent"
            ),
        ]

        _atoms = await adapter.process_and_store(
            messages=messages,
            user_id="dev_user",
            session_id="dev_session",
        )

        # 2. 检索（按 session_id）
        _results = await adapter.adaptive_retrieve(
            session_id="dev_session",
            query="项目技术栈",
        )

        # 验证流程完整
        assert mock_memory_store.put.called
        assert mock_memory_store.search.called
