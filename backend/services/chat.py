"""
Chat Service - 对话服务（基于 LangGraph）

使用 LangGraph 和 LangChain 实现：
- 对话历史管理（通过 LangGraph checkpointer，自动管理）
- 长期记忆存储和检索（LongTermMemoryStore）
"""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.config import get_execution_config_service
from core.engine.langgraph_agent import LangGraphAgentEngine
from core.engine.langgraph_checkpointer import LangGraphCheckpointer
from core.llm.gateway import LLMGateway
from core.memory.langgraph_store import LongTermMemoryStore
from core.memory.simplemem_client import SimpleMemAdapter, SimpleMemConfig
from core.sandbox import SessionManager, SessionRecreationResult
from core.types import AgentConfig, EventType, Message, MessageRole
from db.vector import get_vector_store
from exceptions import NotFoundError
from schemas.message import ChatEvent
from services.agent import AgentService
from services.session import SessionService
from services.title import TitleService
from tools.registry import ConfiguredToolRegistry, ToolRegistry
from utils.logging import get_logger

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
        self.tool_registry = ToolRegistry()  # 默认工具注册表（向后兼容）
        # 使用提供的 checkpointer 或创建新的（优先使用全局单例）
        self.checkpointer = checkpointer or LangGraphCheckpointer(storage_type="postgres")
        self.session_service = SessionService(db)
        self.agent_service = AgentService(db)
        self.title_service = TitleService(db, llm_gateway=self.llm_gateway)
        # 执行环境配置服务
        self.config_service = get_execution_config_service()

        # 初始化长期记忆存储
        try:
            vector_store = get_vector_store()
            self.memory_store = LongTermMemoryStore(
                llm_gateway=self.llm_gateway,
                vector_store=vector_store,
            )
            # 初始化 SimpleMem 适配器（基于 SimpleMem 论文，提供 30x Token 压缩）
            # 使用小模型做记忆提取，节省成本
            self.simplemem = (
                SimpleMemAdapter(
                    llm_gateway=self.llm_gateway,
                    memory_store=self.memory_store,
                    config=SimpleMemConfig(
                        window_size=settings.simplemem_window_size,
                        novelty_threshold=settings.simplemem_novelty_threshold,
                        k_min=3,
                        k_max=15,
                        extraction_model=settings.simplemem_extraction_model,
                    ),
                )
                if settings.simplemem_enabled
                else None
            )
        except Exception as e:
            logger.warning("Memory store initialization failed: %s", e, exc_info=True)
            self.memory_store = None
            self.simplemem = None

        # 后台任务集合（防止被垃圾回收）
        self._background_tasks: set[asyncio.Task] = set()

    async def _ensure_memory_store_initialized(self) -> None:
        """确保记忆存储已初始化"""
        if self.memory_store:
            try:
                await self.memory_store.setup()
            except Exception as e:
                logger.warning("Memory store setup failed: %s", e)

    # pylint: disable=too-many-branches
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
            # 发送对话创建事件（使用类型安全工厂方法）
            yield ChatEvent.session_created(session_id)
        else:
            # 验证对话是否存在且属于当前用户
            session = await self.session_service.get_by_id(session_id)
            if not session:
                raise NotFoundError("Session", session_id)
            if str(session.user_id) != user_id:
                raise NotFoundError("Session", session_id)  # 不泄露权限信息

        # 检查是否需要生成标题（会话无标题且是第一条消息）
        should_generate_title = session and not session.title
        if should_generate_title:
            # 检查消息数量（在添加消息前）
            messages = await self.session_service.get_messages(session_id, skip=0, limit=1)
            is_first_message = len(messages) == 0

            if is_first_message:
                # 异步生成标题（根据第一条消息），不阻塞对话流程
                task = asyncio.create_task(
                    self.title_service.generate_and_update(
                        session_id=session_id,
                        strategy="first_message",
                        message=message,
                        user_id=user_id,
                    )
                )
                # 保存任务引用，防止被垃圾回收
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

        # 保存用户消息到数据库（用于历史记录查询）
        await self.session_service.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=message,
        )

        # 获取 Agent 配置
        agent_config = await self._get_agent_config(agent_id)

        # 加载执行环境配置
        execution_config = self.config_service.load_for_agent(
            agent_id=agent_id or "default",
        )

        # 获取或创建沙箱会话（如果启用 Docker 沙箱）
        if (
            execution_config.sandbox.mode.value == "docker"
            and execution_config.sandbox.docker.session_enabled
        ):
            session_manager = SessionManager.get_instance()
            recreation_result = await session_manager.get_or_create_session_with_info(
                user_id=user_id,
                conversation_id=session_id,
            )

            # 如果是重建的会话（之前被清理过），发送提示事件
            if recreation_result.is_recreated and recreation_result.previous_state:
                yield self._create_session_recreated_event(recreation_result)

        # 创建配置化的工具注册表
        configured_tool_registry = ConfiguredToolRegistry(config=execution_config)

        # 创建 LangGraph Agent Engine
        engine = LangGraphAgentEngine(
            config=agent_config,
            llm_gateway=self.llm_gateway,
            memory_store=self.memory_store,
            tool_registry=configured_tool_registry,
            checkpointer=self.checkpointer,
            execution_config=execution_config,
        )

        # 执行 Agent（LangGraph 会自动管理对话历史）
        final_content = ""
        try:
            async for event in engine.run(
                session_id=session_id,  # 作为 LangGraph 的 thread_id，也用于记忆隔离
                user_id=user_id,
                user_message=message,
            ):
                # AgentEvent 就是 ChatEvent，直接 yield（无需转换）
                yield event

                # 收集最终内容（使用类型安全的数据访问方法）
                if event.type == EventType.TEXT:
                    text_content = event.get_content()
                    if text_content:
                        final_content += text_content
                elif event.type == EventType.DONE:
                    # 使用类型安全的方法获取最终消息
                    final_msg = event.get_final_message()
                    if final_msg:
                        # FinalMessage 自动处理 content 和 reasoning_content
                        msg_content = final_msg.content or final_msg.reasoning_content
                        if msg_content:
                            final_content = msg_content

            # 保存助手消息到数据库（用于历史记录查询）
            if final_content:
                await self.session_service.add_message(
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=final_content,
                )

                # 使用 SimpleMem 提取并存储会话内长程记忆
                # 后台异步执行，不阻塞 SSE 流关闭
                # 记忆按 session_id 隔离，用于在长对话中记住早期内容
                if self.simplemem and session:
                    # 构建消息列表
                    conversation_messages = [
                        Message(role=MessageRole.USER, content=message),
                        Message(role=MessageRole.ASSISTANT, content=final_content),
                    ]
                    # 后台任务：不阻塞主流程
                    task = asyncio.create_task(
                        self._extract_memory_background(conversation_messages, user_id, session_id)
                    )
                    # 防止任务被垃圾回收，完成后自动移除
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)

        except Exception as e:
            logger.error("Chat error for session %s: %s", session_id, e, exc_info=True)
            yield ChatEvent.error(error=str(e), session_id=session_id)

    async def _extract_memory_background(
        self,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> None:
        """后台任务：使用 SimpleMem 提取记忆

        异步执行，不阻塞主流程。失败时只记录日志，不影响用户体验。

        Args:
            messages: 对话消息列表
            user_id: 用户 ID
            session_id: 会话 ID
        """
        try:
            atoms = await self.simplemem.process_and_store(
                messages=messages,
                user_id=user_id,
                session_id=session_id,
            )
            if atoms:
                logger.info(
                    "SimpleMem extracted %d memory atoms for session %s",
                    len(atoms),
                    session_id,
                )
        except Exception as e:
            logger.warning(
                "SimpleMem memory extraction failed for session %s: %s",
                session_id,
                e,
                exc_info=True,
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

    def _create_session_recreated_event(self, result: SessionRecreationResult) -> ChatEvent:
        """创建会话重建事件

        当用户的沙箱环境被清理后重新发送消息时，生成此事件通知前端。

        Args:
            result: 会话重建结果

        Returns:
            会话重建事件
        """
        previous_state = result.previous_state
        data: dict = {
            "session_id": result.session.session_id,
            "is_new": result.is_new,
            "is_recreated": result.is_recreated,
            "message": result.message,
        }

        # 如果有历史状态，添加详细信息
        if previous_state:
            data["previous_state"] = {
                "session_id": previous_state.last_session_id,
                "cleaned_at": (
                    previous_state.last_cleaned_at.isoformat()
                    if previous_state.last_cleaned_at
                    else None
                ),
                "cleanup_reason": (
                    previous_state.cleanup_reason.value if previous_state.cleanup_reason else None
                ),
                "packages_installed": previous_state.installed_packages,
                "files_created": previous_state.created_files,
                "command_count": previous_state.total_commands,
                "total_duration_ms": 0,  # 可以后续添加
            }

        return ChatEvent(
            type="session_recreated",
            data=data,
        )
