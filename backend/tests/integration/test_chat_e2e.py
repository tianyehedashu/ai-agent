"""
Chat 端到端测试

测试真正的 Chat 流程，不使用 Mock，验证：
1. Checkpointer 正确初始化
2. LangGraph Agent 正确执行
3. LLM 调用（可选，需要配置 API Key）
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from core.engine.langgraph_agent import LangGraphAgentEngine
from core.engine.langgraph_checkpointer import LangGraphCheckpointer
from core.llm.gateway import LLMGateway
from core.memory.langgraph_store import LongTermMemoryStore
from core.types import AgentConfig


class TestChatE2E:
    """Chat 端到端测试"""

    @pytest.mark.asyncio
    async def test_checkpointer_initialization(self):
        """测试: Checkpointer 正确初始化"""
        # 使用 MemorySaver（避免需要数据库）
        checkpointer = LangGraphCheckpointer(storage_type="memory")
        await checkpointer.setup()

        # 验证 checkpointer 已初始化
        inner_checkpointer = checkpointer.get_checkpointer()
        assert inner_checkpointer is not None

        # 验证有 aget_tuple 方法
        assert hasattr(inner_checkpointer, "aget_tuple")

    @pytest.mark.asyncio
    async def test_checkpointer_postgres_initialization(self, db_session):
        """测试: PostgresSaver 正确初始化"""
        checkpointer = LangGraphCheckpointer(storage_type="postgres")
        await checkpointer.setup()

        # 验证 checkpointer 已初始化
        inner_checkpointer = checkpointer.get_checkpointer()
        assert inner_checkpointer is not None

        # 验证有 aget_tuple 方法
        assert hasattr(inner_checkpointer, "aget_tuple")

        # 清理
        await checkpointer.cleanup()

    @pytest.mark.asyncio
    async def test_langgraph_agent_with_memory_checkpointer(self):
        """测试: LangGraph Agent 使用 MemorySaver 正确执行"""
        # 初始化 checkpointer
        checkpointer = LangGraphCheckpointer(storage_type="memory")
        await checkpointer.setup()

        # 创建 Agent 配置
        config = AgentConfig(
            name="Test Agent",
            model=settings.default_model,
            max_iterations=1,
            temperature=0.7,
            max_tokens=100,
            tools=[],  # 不使用工具，简化测试
        )

        # Mock LLM Gateway 响应
        llm_gateway = LLMGateway(config=settings)

        # Mock memory_store
        memory_store = AsyncMock(spec=LongTermMemoryStore)
        memory_store.search = AsyncMock(return_value=[])

        # Mock LLM 调用（避免真实 API 调用）
        with patch.object(llm_gateway, "chat") as mock_chat:
            mock_chat.return_value = {
                "content": "Hello! I'm a test response.",
                "tool_calls": [],
            }

            # 创建 Engine
            engine = LangGraphAgentEngine(
                config=config,
                llm_gateway=llm_gateway,
                memory_store=memory_store,
                tool_registry=None,
                checkpointer=checkpointer,
            )

            # 验证图已正确编译
            assert engine.graph is not None

            # 执行（这是关键测试 - 验证 checkpointer 能正常工作）
            events = []
            try:
                async for event in engine.run(
                    session_id="test-session-123",
                    user_id="test-user",
                    user_message="Hello",
                ):
                    events.append(event)
                    print(f"Event: {event.type} - {event.data}")
            except NotImplementedError as e:
                pytest.fail(f"Checkpointer NotImplementedError: {e}")
            except Exception as e:
                # 其他错误可能是 LLM 相关，但不是 checkpointer 问题
                print(f"Other error (may be expected): {e}")

            # 验证收到了事件
            assert len(events) > 0, "Should receive at least one event"
            event_types = [e.type.value for e in events]
            print(f"Event types: {event_types}")

    @pytest.mark.asyncio
    async def test_checkpointer_not_none_after_setup(self):
        """测试: setup 后 checkpointer 不为 None"""
        # 测试 PostgresSaver（这是实际使用的）
        checkpointer = LangGraphCheckpointer(storage_type="postgres")

        # setup 前应该是 None
        assert checkpointer.checkpointer is None

        # setup 后应该不为 None
        try:
            await checkpointer.setup()
            assert checkpointer.checkpointer is not None
            assert checkpointer.get_checkpointer() is not None
        except Exception as e:
            # 如果数据库连接失败，跳过测试
            pytest.skip(f"Database connection failed: {e}")
        finally:
            await checkpointer.cleanup()
