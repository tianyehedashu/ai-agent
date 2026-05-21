"""Chat agent run — engine prep, execution, sandbox/MCP helpers."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from domains.agent.application.chat_engine import LangGraphAgentEngine
import uuid

from bootstrap.config import settings
from domains.agent.domain.types import (
    AgentConfig,
    AgentEvent,
    AgentExecutionLimits,
    EventType,
    Message,
    MessageRole,
)
from domains.agent.infrastructure.sandbox import SandboxCreationResult, SandboxManager
from domains.agent.infrastructure.tools.mcp import MCPToolService
from domains.agent.infrastructure.tools.registry import ConfiguredToolRegistry
from libs.db.database import get_session_context
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.application.chat_use_case import ChatUseCase

logger = get_logger(__name__)


class ChatAgentRunMixin:
    """Agent 对话执行：引擎准备、事件队列执行、沙箱与 MCP 工具加载。"""

    async def _prepare_agent_engine(
        self: ChatUseCase,
        agent_id: str | None,
        session_id: str,
        user_id: str,
        session: object,
        request_model_ref: str | None,
    ) -> tuple[LangGraphAgentEngine, AgentEvent | None, str | None]:
        """准备 Agent 引擎"""
        allowed = await self._visible_text_system_ids()
        picked = await self._pick_chat_model_ref(request_model_ref, session, agent_id)
        resolved = await self._model_resolution.resolve_text_chat_model(
            picked,
            allowed_text_system_ids=allowed,
        )
        agent_config = await self._get_agent_config(agent_id)
        agent_config = agent_config.model_copy(update={"model": resolved.model})

        execution_config = self.config_service.load_for_agent(agent_id=agent_id or "default")

        session_recreated_event = None
        if (
            execution_config.sandbox.mode.value == "docker"
            and execution_config.sandbox.docker.sandbox_enabled
        ):
            sandbox_manager = SandboxManager.get_instance()
            creation_result = await sandbox_manager.get_or_create_with_info(
                user_id=user_id,
                session_id=session_id,
            )
            if creation_result.is_recreated and creation_result.previous_state:
                session_recreated_event = self._create_sandbox_recreated_event(creation_result)

        configured_tool_registry = ConfiguredToolRegistry(config=execution_config)

        await self._load_mcp_tools(session_id, configured_tool_registry)

        from domains.agent.application.chat_engine import LangGraphAgentEngine

        engine = LangGraphAgentEngine(
            config=agent_config,
            llm_gateway=self.llm_gateway,
            memory_store=self.memory_store,
            tool_registry=configured_tool_registry,
            checkpointer=self.checkpointer,
            execution_config=execution_config,
        )

        return engine, session_recreated_event, picked

    async def _execute_agent_with_event_queue(
        self: ChatUseCase,
        engine: LangGraphAgentEngine,
        session_id: str,
        message: str,
        user_id: str,
        session: object | None,
        event_queue: asyncio.Queue[AgentEvent | None],
        human_message_parts: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行 Agent 并保存结果，同时监听事件队列"""
        final_content = ""
        final_token_count = 0
        final_metadata: dict[str, object] = {}
        engine_done = False

        async def engine_task() -> None:
            nonlocal final_content, final_metadata, final_token_count, engine_done
            try:
                async for event in engine.run(
                    session_id=session_id,
                    user_message=message,
                    user_id=user_id,
                    user_message_parts=human_message_parts,
                ):
                    await event_queue.put(event)

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
                        usage = event.data.get("usage")
                        model = event.data.get("model")
                        total_tokens = event.data.get("total_tokens")
                        if isinstance(total_tokens, int):
                            final_token_count = total_tokens
                        if isinstance(usage, dict):
                            final_metadata["usage"] = usage
                        if isinstance(model, str) and model:
                            final_metadata["model"] = model
                engine_done = True
                await event_queue.put(None)
            except Exception as e:
                logger.error("Engine error for session %s: %s", session_id, e, exc_info=True)
                await event_queue.put(AgentEvent.error(error=str(e), session_id=session_id))
                engine_done = True
                await event_queue.put(None)

        engine_task_obj: asyncio.Task[None] | None = None
        try:
            engine_task_obj = asyncio.create_task(engine_task())

            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield event

            if engine_task_obj is not None:
                await engine_task_obj

            if final_content:
                await self._save_assistant_message_and_memory(
                    session_id,
                    message,
                    final_content,
                    user_id,
                    session,
                    metadata=final_metadata,
                    token_count=final_token_count,
                )

        except Exception as e:
            logger.error("Chat error for session %s: %s", session_id, e, exc_info=True)
            yield AgentEvent.error(error=str(e), session_id=session_id)
        finally:
            if engine_task_obj is not None and not engine_task_obj.done():
                engine_task_obj.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await engine_task_obj

    async def _execute_agent_and_save(
        self: ChatUseCase,
        engine: LangGraphAgentEngine,
        session_id: str,
        message: str,
        user_id: str,
        session: object | None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行 Agent 并保存结果。

        .. deprecated::
            内部实现保留用于向后兼容，新代码请使用流式接口。
        """
        async for event in self._execute_agent_with_event_queue(
            engine, session_id, message, user_id, session, asyncio.Queue()
        ):
            yield event

    async def _save_assistant_message_and_memory(
        self: ChatUseCase,
        session_id: str,
        user_message: str,
        final_content: str,
        user_id: str,
        session: object | None,
        metadata: dict[str, object] | None = None,
        token_count: int | None = None,
    ) -> None:
        """保存助手消息并提取记忆"""
        await self.session_use_case.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=final_content,
            metadata=metadata,
            token_count=token_count,
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
        self: ChatUseCase,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> None:
        """后台任务：提取记忆（使用独立的数据库会话）"""
        try:
            sm = self.simplemem
            assert sm is not None
            async with get_session_context():
                atoms = await sm.process_and_store(
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

    async def _get_agent_config(self: ChatUseCase, agent_id: str | None) -> AgentConfig:
        """获取 Agent 配置"""
        if agent_id:
            agent = await self.agent_service.get_agent(agent_id)
            if agent:
                return self._build_config_from_agent(agent)

        return AgentConfig.create_default(
            model=settings.default_model,
            checkpoint_enabled=settings.checkpoint_enabled,
            hitl_enabled=settings.hitl_enabled,
        )

    def _build_config_from_agent(self: ChatUseCase, agent: object) -> AgentConfig:
        """从 Agent 实体构建配置"""
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
            hitl_operations=AgentExecutionLimits.DEFAULT_HITL_OPERATIONS.copy(),
        )

    def _create_sandbox_recreated_event(
        self: ChatUseCase, result: SandboxCreationResult
    ) -> AgentEvent:
        """创建沙箱重建事件"""
        previous_state = result.previous_state
        data: dict[str, object] = {
            "session_id": result.sandbox.sandbox_id,
            "is_new": result.is_new,
            "is_recreated": result.is_recreated,
            "message": result.message,
        }

        if previous_state:
            data["previous_state"] = {
                "session_id": previous_state.last_sandbox_id,
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

    async def _load_mcp_tools(
        self: ChatUseCase, session_id: str, tool_registry: ConfiguredToolRegistry
    ) -> None:
        """加载 Session 配置的 MCP 工具并注册到工具注册表"""
        try:
            session = await self.session_use_case.get_session(session_id)
            if not session:
                logger.warning("Session %s not found, skipping MCP tools", session_id)
                return

            session_config = session.config if isinstance(session.config, dict) else {}
            mcp_config = session_config.get("mcp_config", {})
            enabled_server_ids_raw = mcp_config.get("enabled_servers", [])

            enabled_server_ids: list[uuid.UUID] = []
            for sid in enabled_server_ids_raw:
                try:
                    if isinstance(sid, str):
                        enabled_server_ids.append(uuid.UUID(sid))
                    else:
                        enabled_server_ids.append(sid)
                except (ValueError, AttributeError):
                    logger.warning("Invalid server ID in MCP config: %s", sid)

            if not enabled_server_ids:
                logger.debug("No MCP servers enabled for session %s", session_id)
                return

            mcp_service = MCPToolService(self.db)
            await mcp_service.load_enabled_servers(enabled_server_ids)

            mcp_manager = await mcp_service.initialize_mcp_manager()
            if not mcp_manager:
                logger.warning("Failed to initialize MCP manager for session %s", session_id)
                return

            mcp_tools = await mcp_service.get_mcp_tools()

            for tool in mcp_tools:
                tool_registry.register(tool)
                logger.info(
                    "Registered MCP tool: %s for session %s",
                    tool.name,
                    session_id[:8],
                )

            logger.info(
                "Loaded %d MCP tools for session %s",
                len(mcp_tools),
                session_id[:8],
            )

            await mcp_service.cleanup()

        except Exception as e:
            logger.error(
                "Failed to load MCP tools for session %s: %s",
                session_id,
                e,
                exc_info=True,
            )
