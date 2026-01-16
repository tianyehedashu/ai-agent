"""
Chat Service - 对话服务（基于 LangGraph）

使用 LangGraph 和 LangChain 实现：
- 对话历史管理（通过 LangGraph checkpointer，自动管理）
- 长期记忆存储和检索（LongTermMemoryStore）
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.engine.langgraph_agent import LangGraphAgentEngine
from core.engine.langgraph_checkpointer import LangGraphCheckpointer
from core.llm.gateway import LLMGateway
from core.memory.langgraph_store import LongTermMemoryStore
from core.types import AgentConfig, AgentEvent, EventType, MessageRole
from db.vector import get_vector_store
from exceptions import NotFoundError
from schemas.message import ChatEvent
from services.agent import AgentService
from services.session import SessionService
from tools.registry import ToolRegistry
from utils.logging import get_logger
from utils.serialization import Serializer

logger = get_logger(__name__)


class ChatService:
    """对话服务（基于 LangGraph）

    使用 LangGraph StateGraph 和 checkpointer 实现对话管理：
    - 对话历史自动管理（通过 checkpointer，thread_id = session_id）
    - 长期记忆存储和检索（LongTermMemoryStore）

    Attributes:
        db: 数据库会话
        llm_gateway: LLM 网关
        tool_registry: 工具注册表
        checkpointer: LangGraph 检查点管理器
        memory_store: 长期记忆存储
        session_service: 会话服务
        agent_service: Agent 服务
    """

    def __init__(
        self,
        db: AsyncSession,
        checkpointer: LangGraphCheckpointer | None = None,
    ) -> None:
        self.db = db
        # 通过依赖注入传递配置，避免 Core 层依赖应用层
        self.llm_gateway = LLMGateway(config=settings)
        self.tool_registry = ToolRegistry()
        # 使用提供的 checkpointer 或创建新的（优先使用全局单例）
        self.checkpointer = checkpointer or LangGraphCheckpointer(storage_type="postgres")
        self.session_service = SessionService(db)
        self.agent_service = AgentService(db)

        # 初始化长期记忆存储
        try:
            vector_store = get_vector_store()
            self.memory_store = LongTermMemoryStore(
                llm_gateway=self.llm_gateway,
                vector_store=vector_store,
            )
            # 初始化 Store
            # 注意：这里需要异步初始化，但 __init__ 是同步的
            # 实际初始化在第一次使用时进行
        except Exception as e:
            logger.warning("Memory store initialization failed: %s", e, exc_info=True)
            self.memory_store = None

    async def _ensure_memory_store_initialized(self) -> None:
        """确保记忆存储已初始化"""
        if self.memory_store:
            try:
                await self.memory_store.setup()
            except Exception as e:
                logger.warning("Memory store setup failed: %s", e)

    async def chat(
        self,
        session_id: str | None,
        message: str,
        agent_id: str | None,
        user_id: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """处理对话请求

        Args:
            session_id: 对话 ID (可选，不提供则创建新对话，作为 LangGraph 的 thread_id)
            message: 用户消息
            agent_id: Agent ID (可选)
            user_id: 用户 ID

        Yields:
            ChatEvent: 聊天事件流
        """
        # 确保记忆存储已初始化
        await self._ensure_memory_store_initialized()

        # 创建或获取对话
        session = None
        if not session_id:
            # 创建新对话
            session = await self.session_service.create(
                user_id=user_id,
                agent_id=agent_id,
            )
            session_id = str(session.id)
            # 确保对话已刷新到数据库
            await self.db.flush()
            await self.db.refresh(session)
            # 关键：在发送事件前手动提交事务，确保前端能立即查询到
            await self.db.commit()
            # 发送对话创建事件，通知前端更新 sessionId
            yield ChatEvent(
                type="session_created",
                data={"session_id": session_id},
            )
        else:
            # 验证对话是否存在且属于当前用户
            session = await self.session_service.get_by_id(session_id)
            if not session:
                raise NotFoundError("Session", session_id)
            if str(session.user_id) != user_id:
                raise NotFoundError("Session", session_id)  # 不泄露权限信息

        # 保存用户消息到数据库（用于历史记录查询）
        await self.session_service.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=message,
        )

        # 获取 Agent 配置
        config = await self._get_agent_config(agent_id)

        # 创建 LangGraph Agent Engine
        engine = LangGraphAgentEngine(
            config=config,
            llm_gateway=self.llm_gateway,
            memory_store=self.memory_store,
            tool_registry=self.tool_registry,
            checkpointer=self.checkpointer,
        )

        # 执行 Agent（LangGraph 会自动管理对话历史）
        final_content = ""
        try:
            async for event in engine.run(
                session_id=session_id,  # 作为 LangGraph 的 thread_id
                user_id=user_id,
                user_message=message,
            ):
                # 转换为 ChatEvent
                chat_event = self._convert_event(event)
                yield chat_event

                # 收集最终内容
                if event.type == EventType.TEXT:
                    text_content = event.data.get("content", "")
                    if text_content:
                        final_content += text_content
                elif event.type == EventType.DONE:
                    final_msg = event.data.get("final_message")
                    if final_msg and final_msg.get("content"):
                        final_content = final_msg["content"]

            # 保存助手消息到数据库（用于历史记录查询）
            if final_content:
                await self.session_service.add_message(
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=final_content,
                )

                # 提取并存储长期记忆（异步，不阻塞响应）
                if self.memory_store and session:
                    try:
                        # 记忆提取可以在后台异步进行
                        # 使用 LongTermMemoryStore 存储重要信息
                        logger.info(
                            "Conversation completed for session %s, memory extraction can be done asynchronously",
                            session_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "Memory extraction failed for session %s: %s",
                            session_id,
                            e,
                            exc_info=True,
                        )

        except Exception as e:
            logger.error("Chat error for session %s: %s", session_id, e, exc_info=True)
            yield ChatEvent(
                type="error",
                data={"error": str(e), "session_id": session_id},
            )

    async def _get_agent_config(self, agent_id: str | None) -> AgentConfig:
        """获取 Agent 配置

        从数据库加载 Agent 配置，如果没有指定 agent_id 则返回默认配置。

        Args:
            agent_id: Agent ID（可选）

        Returns:
            Agent 配置对象
        """
        if agent_id:
            agent = await self.agent_service.get_by_id(agent_id)
            if agent:
                return AgentConfig(
                    name=agent.name,
                    model=agent.model,
                    max_iterations=agent.max_iterations,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    tools=agent.tools,
                    system_prompt=agent.system_prompt,
                    checkpoint_enabled=True,
                    checkpoint_interval=5,
                    hitl_enabled=True,
                    hitl_operations=["run_shell", "write_file", "delete_file"],
                )

        # 返回默认配置
        return AgentConfig(
            name="Default Agent",
            model=settings.default_model,
            max_iterations=settings.agent_max_iterations,
            temperature=0.7,
            max_tokens=settings.agent_max_tokens,
            tools=["read_file", "write_file", "list_dir", "run_shell", "search_code"],
            checkpoint_enabled=settings.checkpoint_enabled,
            checkpoint_interval=5,
            hitl_enabled=settings.hitl_enabled,
            hitl_operations=settings.hitl_interrupt_tools,
        )

    def _convert_event(self, event: AgentEvent) -> ChatEvent:
        """转换 AgentEvent 为 ChatEvent

        Args:
            event: Agent 事件

        Returns:
            聊天事件
        """
        type_mapping = {
            EventType.THINKING: "thinking",
            EventType.TEXT: "text",
            EventType.TOOL_CALL: "tool_call",
            EventType.TOOL_RESULT: "tool_result",
            EventType.INTERRUPT: "interrupt",
            EventType.DONE: "done",
            EventType.ERROR: "error",
            EventType.TERMINATED: "terminated",
        }

        # 确保 data 中的 LiteLLM 对象被序列化
        serialized_data = Serializer.serialize_dict(event.data)

        return ChatEvent(
            type=type_mapping.get(event.type, str(event.type)),
            data=serialized_data,
            timestamp=event.timestamp,
        )
