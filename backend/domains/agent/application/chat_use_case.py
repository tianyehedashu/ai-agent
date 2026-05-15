"""
Chat Use Case - 对话用例

编排对话相关的操作，包括会话管理、消息处理、Agent 执行。不包含业务逻辑，只负责协调。
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any, Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.agent.application import AgentUseCase
from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.agent.domain.types import (
    AgentConfig,
    AgentEvent,
    AgentExecutionLimits,
    EventType,
    Message,
    MessageRole,
)
from domains.agent.infrastructure.engine.langgraph_agent import LangGraphAgentEngine
from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.llm import create_image_generator
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.agent.infrastructure.memory.simplemem_client import SimpleMemAdapter, SimpleMemConfig
from domains.agent.infrastructure.sandbox import SandboxCreationResult, SandboxManager
from domains.agent.infrastructure.tools.mcp import MCPToolService
from domains.agent.infrastructure.tools.registry import ConfiguredToolRegistry, ToolRegistry
from domains.gateway.application.gateway_internal_log_context import (
    reset_internal_store_full_override,
    resolve_internal_store_full_messages,
    set_internal_store_full_override,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.session.application import TitleUseCase
from domains.session.application.ports import SessionApplicationPort
from libs.config import get_execution_config_service
from libs.db.database import get_session_context
from libs.db.vector import get_vector_store
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

_CHAT_MODEL_REF_PENDING = object()


class ChatUseCase:
    """对话用例

    协调对话相关的操作，使用领域服务进行业务规则验证。
    """

    def __init__(
        self,
        db: AsyncSession,
        session_use_case: SessionApplicationPort,
        session_use_case_factory: Callable[[AsyncSession], SessionApplicationPort],
        checkpointer: LangGraphCheckpointer | None = None,
        model_catalog: ModelCatalogPort | None = None,
        user_model_use_case: UserModelUseCase | None = None,
    ) -> None:
        self.db = db
        self.llm_gateway = LLMGateway(config=settings, model_catalog=model_catalog)
        self._model_catalog = model_catalog
        if user_model_use_case is None:
            if model_catalog is None:
                raise ValueError("ChatUseCase requires model_catalog when user_model_use_case is omitted")
            user_model_use_case = UserModelUseCase(db, catalog=model_catalog)
        self._user_models = user_model_use_case
        self.tool_registry = ToolRegistry()
        self.checkpointer = checkpointer or LangGraphCheckpointer(storage_type="postgres")
        self.session_use_case = session_use_case
        self._session_use_case_factory = session_use_case_factory
        self.agent_service = AgentUseCase(db)

        self.title_service = TitleUseCase(db, llm_gateway=self.llm_gateway)

        # 执行环境配置服务
        self.config_service = get_execution_config_service()

        # 初始化长期记忆存储
        self._init_memory_store()

        # 后台任务集合
        self._background_tasks: set[asyncio.Task] = set()

        # 事件队列（用于后台任务发送事件）
        self._event_queues: dict[str, asyncio.Queue[AgentEvent | None]] = {}

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
        mcp_config: dict | None = None,
        model_ref: str | None = None,
        gateway_verbose_request_log: bool | None = None,
        creative_mode: str = "chat",
        reference_image_urls: list[str] | None = None,
        image_gen_strength: float | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """处理对话请求

        Args:
            session_id: 对话 ID
            message: 用户消息
            agent_id: Agent ID
            user_id: 用户 ID
            mcp_config: MCP 配置（仅新会话生效，如 {"enabled_servers": [...]}）
            model_ref: 系统模型 id 或用户模型 UUID；None 表示按会话存储 / Agent / 默认解析
            gateway_verbose_request_log: 单次请求是否扩展网关调用日志（受服务端配置约束）
            creative_mode: chat（默认 Agent 对话）| image_gen（直连 ImageGenerator）
            reference_image_urls: 参考图 URL（http/https）；对话+视觉模型时注入多模态用户消息
            image_gen_strength: 图生图强度 0~1（仅 image_gen + 有参考图时生效）

        Yields:
            AgentEvent: 聊天事件
        """
        await self._ensure_memory_store_initialized()

        mode = (creative_mode or "chat").strip().lower()
        if mode not in ("chat", "image_gen"):
            yield AgentEvent.error(error=f"不支持的创作模式: {creative_mode}", session_id=session_id)
            return

        ref_urls = self._normalize_reference_image_urls(reference_image_urls or [])

        # 创建或获取对话
        session, session_id, is_new_session = await self._get_or_create_session(
            session_id, user_id, agent_id
        )

        user_metadata = self._build_user_message_metadata(mode, ref_urls)

        if is_new_session:
            # 新建会话：先落库并提交首条用户消息；session_created 延至解析并写入 chat_model_ref 之后，
            # 避免前端 navigate 后 GET 会话尚无 chat_model_ref 而把模型选择器重置为默认。
            await self.session_use_case.add_message(
                session_id=session_id,
                role=MessageRole.USER,
                content=message,
                metadata=user_metadata,
            )
            await self.db.commit()
            if mcp_config and mcp_config.get("enabled_servers"):
                await self.session_use_case.update_session_mcp_config(
                    session_id, mcp_config["enabled_servers"]
                )

        # 为当前会话创建事件队列（用于后台任务发送事件）
        event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        self._event_queues[session_id] = event_queue

        session_cfg = session.config if session and isinstance(getattr(session, "config", None), dict) else None
        log_override = resolve_internal_store_full_messages(
            request_explicit=gateway_verbose_request_log,
            session_config=session_cfg,
        )
        log_token = None
        if log_override is not None:
            log_token = set_internal_store_full_override(log_override)

        picked_chat_model_for_persist: object = _CHAT_MODEL_REF_PENDING

        try:
            # 处理标题生成
            await self._handle_title_generation(session, session_id, message, user_id)

            # 保存用户消息（仅非新建会话：新建会话已在上面写入并提交）
            if not is_new_session:
                await self.session_use_case.add_message(
                    session_id=session_id,
                    role=MessageRole.USER,
                    content=message,
                    metadata=user_metadata,
                )

            if mode == "image_gen":
                async for evt in self._run_image_gen_mode(
                    session_id=session_id,
                    message=message,
                    session=session,
                    model_ref=model_ref,
                    reference_image_urls=ref_urls,
                    image_gen_strength=image_gen_strength,
                    is_new_session=is_new_session,
                ):
                    yield evt
                return

            human_multimodal: list[dict[str, Any]] | None = None
            if mode == "chat" and ref_urls:
                try:
                    human_multimodal = await self._build_vision_user_content(
                        message=message,
                        reference_image_urls=ref_urls,
                        request_model_ref=model_ref,
                        session=session,
                        agent_id=agent_id,
                    )
                except ValidationError as e:
                    yield AgentEvent.error(error=e.message, session_id=session_id)
                    return

            # 准备 Agent 引擎
            try:
                engine, session_recreated_event, picked_chat_model_for_persist = (
                    await self._prepare_agent_engine(
                        agent_id, session_id, user_id, session, model_ref
                    )
                )
            except ValidationError as e:
                yield AgentEvent.error(error=e.message, session_id=session_id)
                return

            # 在流式输出前写入，避免前端 GET 会话时尚无 chat_model_ref 而把选择器重置为默认。
            await self._persist_picked_chat_model_ref(session_id, picked_chat_model_for_persist)

            if is_new_session:
                yield AgentEvent.session_created(session_id)

            if session_recreated_event:
                yield session_recreated_event

            # 执行 Agent，同时监听事件队列
            async for event in self._execute_agent_with_event_queue(
                engine,
                session_id,
                message,
                user_id,
                session,
                event_queue,
                human_message_parts=human_multimodal,
            ):
                yield event
        finally:
            if log_token is not None:
                reset_internal_store_full_override(log_token)
            # 清理事件队列
            self._event_queues.pop(session_id, None)

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
        """获取或创建会话（复用 Session 域统一入口）"""
        try:
            session, is_new = await self.session_use_case.get_or_create_session_for_principal(
                principal_id=user_id,
                session_id=session_id,
                agent_id=agent_id,
            )
        except Exception:
            raise NotFoundError("Session", session_id or "") from None

        resolved_session_id = str(session.id)
        if is_new:
            await self.db.flush()
            await self.db.refresh(session)
            await self.db.commit()
        return session, resolved_session_id, is_new

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
        if message_count <= 1:
            # 无标题且消息数 ≤ 1 时触发（新建会话首条已提前落库时为 1）
            # 创建后台任务，使用独立的数据库会话
            task = asyncio.create_task(
                self._generate_title_background(session_id, message, user_id)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _generate_title_background(self, session_id: str, message: str, user_id: str) -> None:
        """后台任务：生成标题（使用独立的数据库会话）"""
        try:
            # 使用独立的数据库会话，避免与主请求会话冲突
            async with get_session_context() as db:
                title_service = TitleUseCase(db, llm_gateway=self.llm_gateway)
                success = await title_service.generate_and_update(
                    session_id=session_id,
                    strategy="first_message",
                    message=message,
                    user_id=user_id,
                )

                # 如果标题生成成功，发送标题更新事件
                if success:
                    # 获取更新后的标题（使用独立 db 的 session 能力）
                    session_use_case = self._session_use_case_factory(db)
                    session = await session_use_case.get_session(session_id)
                    if session and session.title:
                        # 将事件放入队列（如果队列存在）
                        event_queue = self._event_queues.get(session_id)
                        if event_queue:
                            title_event = AgentEvent.title_updated(
                                session_id=session_id, title=session.title
                            )
                            await event_queue.put(title_event)
                            logger.debug(
                                "Sent title_updated event for session %s: %s",
                                session_id[:8],
                                session.title,
                            )
        except Exception as e:
            logger.warning(
                "Background title generation failed for session %s: %s",
                session_id,
                e,
                exc_info=True,
            )

    async def _visible_text_system_ids(self) -> frozenset[str]:
        if self._model_catalog is None:
            return frozenset()
        team_id = resolve_internal_gateway_team_id()
        rows = await self._model_catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="text",
        )
        return frozenset(str(r["id"]) for r in rows if r.get("id") is not None)

    async def _pick_chat_model_ref(
        self,
        request_model_ref: str | None,
        session: object,
        agent_id: str | None,
    ) -> str | None:
        """解析用户可见的 model_ref：请求 > 会话存储 > Agent（须合法）> 默认（None）。"""
        if request_model_ref and str(request_model_ref).strip():
            return str(request_model_ref).strip()
        cfg = session.config if isinstance(getattr(session, "config", None), dict) else {}
        stored = cfg.get("chat_model_ref")
        if isinstance(stored, str) and stored.strip():
            ref = stored.strip()
            try:
                sid = uuid.UUID(ref)
            except ValueError:
                return ref
            row = await self._user_models.repo.get_owned(sid)
            if (
                row
                and row.is_active
                and "text" in list(row.model_types or [])
                and row.last_test_status != "failed"
            ):
                return ref
        allowed = await self._visible_text_system_ids()
        base = await self._get_agent_config(agent_id)
        agent_litellm = base.model
        if agent_litellm in allowed:
            return agent_litellm
        try:
            uid = uuid.UUID(str(agent_litellm))
        except (ValueError, AttributeError, TypeError):
            return None
        row = await self._user_models.repo.get_owned(uid)
        if (
            row
            and row.is_active
            and "text" in list(row.model_types or [])
            and row.last_test_status != "failed"
        ):
            return str(uid)
        return None

    async def _persist_picked_chat_model_ref(self, session_id: str, picked: object) -> None:
        """将本次解析到的对话模型引用写入会话（在流式输出前调用，避免前端 GET 竞态）。"""
        if picked is _CHAT_MODEL_REF_PENDING:
            return
        if not isinstance(picked, str | type(None)):
            logger.warning(
                "Unexpected picked_chat_model_for_persist type, skip persist (session %s)",
                session_id[:8],
            )
            return
        try:
            await self.session_use_case.update_session_chat_model_ref(
                session_id,
                picked,
                flush=False,
            )
            await self.db.flush()
        except Exception:
            logger.warning(
                "Failed to persist chat_model_ref for session %s",
                session_id[:8],
                exc_info=True,
            )

    @staticmethod
    def _normalize_reference_image_urls(raw: list[str]) -> list[str]:
        out: list[str] = []
        for item in raw:
            u = str(item).strip()
            if u.startswith("http://") or u.startswith("https://"):
                out.append(u)
        return out

    @staticmethod
    def _build_user_message_metadata(creative_mode: str, reference_image_urls: list[str]) -> dict[str, Any]:
        meta: dict[str, Any] = {"creative_mode": creative_mode}
        if reference_image_urls:
            meta["reference_image_urls"] = reference_image_urls
        return meta

    async def _pick_image_gen_model_ref(
        self, request_model_ref: str | None, session: object
    ) -> str | None:
        if request_model_ref and str(request_model_ref).strip():
            return str(request_model_ref).strip()
        cfg = session.config if isinstance(getattr(session, "config", None), dict) else {}
        stored = cfg.get("image_gen_model_ref")
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
        return None

    async def _max_reference_images_for_model(self, model_key: str) -> int:
        if self._model_catalog is None:
            return 8
        snap = await self._model_catalog.resolve_capabilities(model_key)
        if snap is None:
            return 8
        return snap.max_reference_images if snap.max_reference_images > 0 else 8

    async def _supports_img2img(self, model_key: str) -> bool:
        if self._model_catalog is None:
            return True
        snap = await self._model_catalog.resolve_capabilities(model_key)
        if snap is None:
            return True
        return snap.supports_img2img

    async def _run_image_gen_mode(
        self,
        *,
        session_id: str,
        message: str,
        session: object,
        model_ref: str | None,
        reference_image_urls: list[str],
        image_gen_strength: float | None,
        is_new_session: bool,
    ) -> AsyncGenerator[AgentEvent, None]:
        allowed = await self._user_models.visible_image_gen_system_model_ids()
        picked_ref = await self._pick_image_gen_model_ref(model_ref, session)
        try:
            resolved = await self._user_models.resolve_image_gen_model_for_chat(
                picked_ref,
                allowed_image_gen_system_ids=allowed,
            )
        except ValidationError as e:
            yield AgentEvent.error(error=e.message, session_id=session_id)
            return

        persist_ref: str | None = picked_ref
        if persist_ref is None and allowed:
            persist_ref = sorted(allowed)[0]

        model_key_for_caps = persist_ref or ""
        if not model_key_for_caps and resolved.is_system:
            model_key_for_caps = (
                f"{resolved.provider}/{resolved.model}" if resolved.model else resolved.provider
            )

        max_refs = await self._max_reference_images_for_model(model_key_for_caps)
        if len(reference_image_urls) > max_refs:
            yield AgentEvent.error(
                error=f"参考图过多：最多 {max_refs} 张",
                session_id=session_id,
            )
            return

        if reference_image_urls and not await self._supports_img2img(model_key_for_caps):
            yield AgentEvent.error(
                error="当前图像生成模型不支持参考图（图生图）",
                session_id=session_id,
            )
            return

        if resolved.provider not in ("volcengine", "openai"):
            yield AgentEvent.error(
                error=f"对话生图暂不支持提供商: {resolved.provider}",
                session_id=session_id,
            )
            return

        await self.session_use_case.merge_session_config_fragment(
            session_id,
            {
                "creative_mode": "image_gen",
                **({"image_gen_model_ref": persist_ref} if persist_ref else {}),
            },
            flush=False,
        )
        await self.db.flush()

        if is_new_session:
            yield AgentEvent.session_created(session_id)

        ref_url = reference_image_urls[0] if reference_image_urls else None
        prov: Literal["volcengine", "openai"] = "volcengine" if resolved.provider == "volcengine" else "openai"

        yield AgentEvent.thinking(status="image_gen", iteration=1, content="正在生成图像…")
        gen = create_image_generator(settings)
        result = await gen.generate(
            prompt=message,
            provider=prov,
            model=resolved.model,
            reference_image_url=ref_url,
            strength=image_gen_strength,
            api_key_override=resolved.api_key,
            api_base_override=resolved.api_base,
        )
        if not result.success:
            yield AgentEvent.error(error=result.error or "图像生成失败", session_id=session_id)
            return

        lines: list[str] = []
        for url in result.images:
            lines.append(f"![generated]({url})")
        markdown = "\n\n".join(lines) if lines else "（未返回图像 URL）"

        await self.session_use_case.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=markdown,
            metadata={
                "kind": "image_gen",
                "image_urls": result.images,
                "usage": result.usage or {},
            },
        )
        await self.db.commit()

        yield AgentEvent.text(markdown)
        yield AgentEvent.done(
            content=markdown,
            iterations=1,
            tool_iterations=0,
            total_tokens=0,
            usage=None,
            model=resolved.model,
        )

    async def _build_vision_user_content(
        self,
        *,
        message: str,
        reference_image_urls: list[str],
        request_model_ref: str | None,
        session: object,
        agent_id: str | None,
    ) -> list[dict[str, Any]]:
        picked = await self._pick_chat_model_ref(request_model_ref, session, agent_id)
        if picked is None:
            raise ValidationError("未选择对话模型，无法发送带参考图的对话（请先选择支持视觉的模型）")
        caps = await self._model_catalog.resolve_capabilities(picked) if self._model_catalog else None
        if caps is None or not caps.supports_vision:
            raise ValidationError("当前对话模型不支持视觉输入，请更换支持「图片理解」的模型或移除参考图")
        max_refs = caps.max_reference_images if caps.max_reference_images > 0 else 8
        if len(reference_image_urls) > max_refs:
            raise ValidationError(f"参考图过多：当前模型最多接受 {max_refs} 张")
        parts: list[dict[str, Any]] = [{"type": "text", "text": message}]
        for url in reference_image_urls[:max_refs]:
            parts.append({"type": "image_url", "image_url": {"url": url}})
        return parts

    async def _prepare_agent_engine(
        self,
        agent_id: str | None,
        session_id: str,
        user_id: str,
        session: object,
        request_model_ref: str | None,
    ) -> tuple[LangGraphAgentEngine, AgentEvent | None]:
        """准备 Agent 引擎"""
        allowed = await self._visible_text_system_ids()
        picked = await self._pick_chat_model_ref(request_model_ref, session, agent_id)
        resolved = await self._user_models.resolve_text_chat_model(
            picked,
            allowed_text_system_ids=allowed,
        )
        agent_config = await self._get_agent_config(agent_id)
        agent_config = agent_config.model_copy(
            update={
                "model": resolved.model,
                "llm_api_key": resolved.api_key,
                "llm_api_base": resolved.api_base,
            }
        )

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

        # 集成 MCP 工具
        await self._load_mcp_tools(session_id, configured_tool_registry)

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
        self,
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

        # 创建引擎任务
        async def engine_task():
            nonlocal final_content, final_metadata, final_token_count, engine_done
            try:
                async for event in engine.run(
                    session_id=session_id,
                    user_message=message,
                    user_id=user_id,
                    user_message_parts=human_message_parts,
                ):
                    # 将引擎事件放入队列
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
                # 发送结束标记
                await event_queue.put(None)
            except Exception as e:
                logger.error("Engine error for session %s: %s", session_id, e, exc_info=True)
                await event_queue.put(AgentEvent.error(error=str(e), session_id=session_id))
                engine_done = True
                await event_queue.put(None)

        try:
            # 启动引擎任务
            engine_task_obj = asyncio.create_task(engine_task())

            # 从队列中获取事件并 yield
            while True:
                event = await event_queue.get()
                if event is None:
                    # 引擎已完成
                    break
                yield event

            # 等待引擎任务完成
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

    async def _execute_agent_and_save(
        self,
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
        self,
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
        self,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> None:
        """后台任务：提取记忆（使用独立的数据库会话）"""
        try:
            sm = self.simplemem
            assert sm is not None
            # 使用独立的数据库会话上下文，确保后台任务不会与主请求会话冲突
            # 虽然 SimpleMem 和 LongTermMemoryStore 使用自己的数据库连接，
            # 但为了保持一致性和安全性，我们仍然使用独立的会话上下文
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

    async def _get_agent_config(self, agent_id: str | None) -> AgentConfig:
        """获取 Agent 配置

        优先使用数据库中存储的 Agent 配置，否则使用默认配置。
        默认配置由 domain 层的 AgentConfig.create_default() 提供，
        但允许通过 settings 覆盖部分参数。
        """
        if agent_id:
            agent = await self.agent_service.get_agent(agent_id)
            if agent:
                return self._build_config_from_agent(agent)

        # 使用 domain 层的默认工厂，但允许 settings 覆盖关键参数
        return AgentConfig.create_default(
            model=settings.default_model,
            checkpoint_enabled=settings.checkpoint_enabled,
            hitl_enabled=settings.hitl_enabled,
        )

    def _build_config_from_agent(self, agent: object) -> AgentConfig:
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

    def _create_sandbox_recreated_event(self, result: SandboxCreationResult) -> AgentEvent:
        """创建沙箱重建事件

        注意：事件类型和字段名使用 session_* 命名（面向用户的接口概念），
        而不是内部实现的 sandbox_* 命名。
        """
        previous_state = result.previous_state
        data: dict = {
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

    async def _load_mcp_tools(self, session_id: str, tool_registry: ConfiguredToolRegistry) -> None:
        """
        加载 Session 配置的 MCP 工具并注册到工具注册表

        Args:
            session_id: 会话 ID
            tool_registry: 工具注册表
        """
        try:
            # 获取 Session 实体
            session = await self.session_use_case.get_session(session_id)
            if not session:
                logger.warning("Session %s not found, skipping MCP tools", session_id)
                return

            # 从 session.config 读取 MCP 配置
            session_config = session.config if isinstance(session.config, dict) else {}
            mcp_config = session_config.get("mcp_config", {})
            enabled_server_ids_raw = mcp_config.get("enabled_servers", [])

            # 转换 UUID（JSONB 存储为字符串）
            enabled_server_ids = []
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

            # 创建 MCP 工具服务
            mcp_service = MCPToolService(self.db)

            # 加载启用的服务器
            await mcp_service.load_enabled_servers(enabled_server_ids)

            # 初始化 MCP 管理器
            mcp_manager = await mcp_service.initialize_mcp_manager()
            if not mcp_manager:
                logger.warning("Failed to initialize MCP manager for session %s", session_id)
                return

            # 获取 MCP 工具
            mcp_tools = await mcp_service.get_mcp_tools()

            # 注册到工具注册表
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

            # 清理资源
            await mcp_service.cleanup()

        except Exception as e:
            logger.error(
                "Failed to load MCP tools for session %s: %s",
                session_id,
                e,
                exc_info=True,
            )
