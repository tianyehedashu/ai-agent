"""
Chat Use Case - 对话用例

编排对话相关的操作，包括会话管理、消息处理、Agent 执行。不包含业务逻辑，只负责协调。
"""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.agent.application import AgentUseCase
from domains.agent.application.session_use_case import SessionUseCase
from domains.agent.domain.entities.session import SessionOwner
from domains.agent.domain.types import (
    AgentConfig,
    AgentEvent,
    EventType,
    Message,
    MessageRole,
)
from domains.agent.infrastructure.engine.langgraph_agent import LangGraphAgentEngine
from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.agent.infrastructure.memory.simplemem_client import SimpleMemAdapter, SimpleMemConfig
from domains.agent.infrastructure.sandbox import SessionManager, SessionRecreationResult
from domains.agent.infrastructure.tools.registry import ConfiguredToolRegistry, ToolRegistry
from domains.identity.domain.types import Principal
from exceptions import NotFoundError
from libs.config import get_execution_config_service
from libs.db.database import get_session_context
from libs.db.vector import get_vector_store
from utils.logging import get_logger

logger = get_logger(__name__)


class ChatUseCase:
    """对话用例

    协调对话相关的操作，使用领域服务进行业务规则验证。
    """

    def __init__(
        self,
        db: AsyncSession,
        checkpointer: LangGraphCheckpointer | None = None,
    ) -> None:
        self.db = db
        self.llm_gateway = LLMGateway(config=settings)
        self.tool_registry = ToolRegistry()
        self.checkpointer = checkpointer or LangGraphCheckpointer(storage_type="postgres")

        # 使用新的 SessionUseCase
        self.session_use_case = SessionUseCase(db)
        self.agent_service = AgentUseCase(db)

        # 延迟导入 TitleUseCase（避免循环依赖）
        # pylint: disable=import-outside-toplevel
        from domains.agent.application.title_use_case import TitleUseCase

        self.title_service = TitleUseCase(db, llm_gateway=self.llm_gateway)

        # 执行环境配置服务
        self.config_service = get_execution_config_service()

        # 初始化长期记忆存储
        self._init_memory_store()

        # 后台任务集合
        self._background_tasks: set[asyncio.Task] = set()

    def _init_memory_store(self) -> None:
        """初始化记忆存储"""
        try:
            vector_store = get_vector_store()
            self.memory_store = LongTermMemoryStore(
                llm_gateway=self.llm_gateway,
                vector_store=vector_store,
            )
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
    ) -> AsyncGenerator[AgentEvent, None]:
        """处理对话请求

        Args:
            session_id: 对话 ID
            message: 用户消息
            agent_id: Agent ID
            user_id: 用户 ID

        Yields:
            AgentEvent: 聊天事件
        """
        await self._ensure_memory_store_initialized()

        # 创建或获取对话
        session, session_id, is_new_session = await self._get_or_create_session(
            session_id, user_id, agent_id
        )

        if is_new_session:
            yield AgentEvent.session_created(session_id)

        # 处理标题生成
        await self._handle_title_generation(session, session_id, message, user_id)

        # 保存用户消息
        await self.session_use_case.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=message,
        )

        # 准备 Agent 引擎
        engine, session_recreated_event = await self._prepare_agent_engine(
            agent_id, session_id, user_id
        )

        if session_recreated_event:
            yield session_recreated_event

        # 执行 Agent
        async for event in self._execute_agent_and_save(
            engine, session_id, message, user_id, session
        ):
            yield event

    async def resume(
        self,
        session_id: str,
        checkpoint_id: str,
        action: str,
        modified_args: dict | None,
        user_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """恢复中断的执行（Human-in-the-Loop）。

        占位实现：目前仅返回错误事件，完整实现需对接 LangGraph 检查点恢复。
        """
        yield AgentEvent.error(
            error="Resume (HITL) not yet implemented in ChatUseCase",
            session_id=session_id,
        )

    async def _get_or_create_session(
        self,
        session_id: str | None,
        user_id: str,
        agent_id: str | None,
    ) -> tuple[object | None, str, bool]:
        """获取或创建会话"""
        is_anonymous = Principal.is_anonymous_id(user_id)

        if not session_id:
            # 创建新对话
            if is_anonymous:
                session = await self.session_use_case.create_session(
                    anonymous_user_id=Principal.extract_anonymous_id(user_id),
                    agent_id=agent_id,
                )
            else:
                session = await self.session_use_case.create_session(
                    user_id=user_id,
                    agent_id=agent_id,
                )
            session_id = str(session.id)
            await self.db.flush()
            await self.db.refresh(session)
            await self.db.commit()
            return session, session_id, True

        # 验证所有权
        owner = SessionOwner.from_principal_id(user_id, is_anonymous)
        try:
            session = await self.session_use_case.get_session_with_ownership_check(
                session_id, owner
            )
        except Exception:
            raise NotFoundError("Session", session_id) from None

        return session, session_id, False

    async def _handle_title_generation(
        self,
        session: object | None,
        session_id: str,
        message: str,
        user_id: str,
    ) -> None:
        """处理标题生成"""
        if not session or session.title:
            return

        message_count = await self.session_use_case.count_messages(session_id)
        if message_count == 0:
            # 创建后台任务，使用独立的数据库会话
            task = asyncio.create_task(
                self._generate_title_background(session_id, message, user_id)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _generate_title_background(
        self, session_id: str, message: str, user_id: str
    ) -> None:
        """后台任务：生成标题（使用独立的数据库会话）"""
        try:
            # 使用独立的数据库会话，避免与主请求会话冲突
            async with get_session_context() as db:
                from domains.agent.application.title_use_case import TitleUseCase

                title_service = TitleUseCase(db, llm_gateway=self.llm_gateway)
                await title_service.generate_and_update(
                    session_id=session_id,
                    strategy="first_message",
                    message=message,
                    user_id=user_id,
                )
        except Exception as e:
            logger.warning(
                "Background title generation failed for session %s: %s",
                session_id,
                e,
                exc_info=True,
            )

    async def _prepare_agent_engine(
        self,
        agent_id: str | None,
        session_id: str,
        user_id: str,
    ) -> tuple[LangGraphAgentEngine, AgentEvent | None]:
        """准备 Agent 引擎"""
        agent_config = await self._get_agent_config(agent_id)
        execution_config = self.config_service.load_for_agent(agent_id=agent_id or "default")

        session_recreated_event = None
        if (
            execution_config.sandbox.mode.value == "docker"
            and execution_config.sandbox.docker.session_enabled
        ):
            session_manager = SessionManager.get_instance()
            recreation_result = await session_manager.get_or_create_session_with_info(
                user_id=user_id,
                conversation_id=session_id,
            )
            if recreation_result.is_recreated and recreation_result.previous_state:
                session_recreated_event = self._create_session_recreated_event(recreation_result)

        configured_tool_registry = ConfiguredToolRegistry(config=execution_config)

        engine = LangGraphAgentEngine(
            config=agent_config,
            llm_gateway=self.llm_gateway,
            memory_store=self.memory_store,
            tool_registry=configured_tool_registry,
            checkpointer=self.checkpointer,
            execution_config=execution_config,
        )

        return engine, session_recreated_event

    async def _execute_agent_and_save(
        self,
        engine: LangGraphAgentEngine,
        session_id: str,
        message: str,
        user_id: str,
        session: object | None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行 Agent 并保存结果"""
        final_content = ""
        try:
            async for event in engine.run(
                session_id=session_id,
                user_message=message,
                user_id=user_id,
            ):
                yield event

                if event.type == EventType.TEXT:
                    text_content = event.get_content()
                    if text_content:
                        final_content += text_content
                elif event.type == EventType.DONE:
                    final_msg = event.get_final_message()
                    if final_msg:
                        msg_content = final_msg.content or final_msg.reasoning_content
                        if msg_content:
                            final_content = msg_content

            if final_content:
                await self._save_assistant_message_and_memory(
                    session_id, message, final_content, user_id, session
                )

        except Exception as e:
            logger.error("Chat error for session %s: %s", session_id, e, exc_info=True)
            yield AgentEvent.error(error=str(e), session_id=session_id)

    async def _save_assistant_message_and_memory(
        self,
        session_id: str,
        user_message: str,
        final_content: str,
        user_id: str,
        session: object | None,
    ) -> None:
        """保存助手消息并提取记忆"""
        await self.session_use_case.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=final_content,
        )

        if self.simplemem and session:
            conversation_messages = [
                Message(role=MessageRole.USER, content=user_message),
                Message(role=MessageRole.ASSISTANT, content=final_content),
            ]
            task = asyncio.create_task(
                self._extract_memory_background(conversation_messages, user_id, session_id)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _extract_memory_background(
        self,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> None:
        """后台任务：提取记忆（使用独立的数据库会话）"""
        try:
            # SimpleMem 可能需要访问数据库，使用独立的会话
            # 注意：SimpleMem 内部可能使用自己的数据库连接，这里主要是为了安全
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
        """获取 Agent 配置"""
        if agent_id:
            agent = await self.agent_service.get_agent(agent_id)
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

    def _create_session_recreated_event(self, result: SessionRecreationResult) -> AgentEvent:
        """创建会话重建事件"""
        previous_state = result.previous_state
        data: dict = {
            "session_id": result.session.session_id,
            "is_new": result.is_new,
            "is_recreated": result.is_recreated,
            "message": result.message,
        }

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
                "total_duration_ms": 0,
            }

        return AgentEvent(
            type="session_recreated",
            data=data,
        )
