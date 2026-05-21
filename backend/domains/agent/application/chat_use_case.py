"""
Chat Use Case - 对话用例

编排对话相关的操作，包括会话管理、消息处理、Agent 执行。不包含业务逻辑，只负责协调。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.agent.application.agent_use_case import AgentUseCase
from domains.agent.application.chat_agent_run import ChatAgentRunMixin
from domains.agent.application.chat_engine import LangGraphAgentEngine
from domains.agent.application.chat_image_gen import ChatImageGenMixin
from domains.agent.application.chat_model_resolution_use_case import ChatModelResolutionUseCase
from domains.agent.domain.types import AgentEvent, MessageRole
from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade
from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.agent.infrastructure.memory.simplemem_client import SimpleMemAdapter, SimpleMemConfig
from domains.agent.infrastructure.tools.registry import ToolRegistry
from domains.gateway.application.gateway_internal_log_context import (
    reset_internal_store_full_override,
    resolve_internal_store_full_messages,
    set_internal_store_full_override,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from libs.config import get_execution_config_service
from libs.db.database import get_session_context
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.application.memory_indexing_service import MemoryIndexingService
    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
    from domains.session.application.ports import SessionApplicationPort

logger = get_logger(__name__)

_CHAT_MODEL_REF_PENDING = object()

# Re-export for tests that patch ``chat_use_case.LangGraphAgentEngine`` / ``get_session_context``.
__all__ = ["ChatUseCase", "LangGraphAgentEngine", "get_session_context"]


class ChatUseCase(ChatImageGenMixin, ChatAgentRunMixin):
    """对话用例

    协调对话相关的操作，使用领域服务进行业务规则验证。
    """

    def __init__(
        self,
        db: AsyncSession,
        session_use_case: SessionApplicationPort,
        session_use_case_factory: Callable[[AsyncSession], SessionApplicationPort],
        memory_indexing: MemoryIndexingService,
        checkpointer: LangGraphCheckpointer | None = None,
        model_catalog: ModelCatalogPort | None = None,
        model_resolution_use_case: ChatModelResolutionUseCase | None = None,
    ) -> None:
        self.db = db
        self.llm_gateway = AgentLlmFacade(config=settings, model_catalog=model_catalog)
        self._model_catalog = model_catalog
        if model_resolution_use_case is None:
            if model_catalog is None:
                raise ValueError(
                    "ChatUseCase requires model_catalog when model_resolution_use_case is omitted"
                )
            model_resolution_use_case = ChatModelResolutionUseCase(db, catalog=model_catalog)
        self._model_resolution = model_resolution_use_case
        self.tool_registry = ToolRegistry()
        self.checkpointer = checkpointer or LangGraphCheckpointer(storage_type="postgres")
        self.session_use_case = session_use_case
        self._session_use_case_factory = session_use_case_factory
        self.agent_service = AgentUseCase(db)

        from domains.session.application.title_use_case import TitleUseCase

        self.title_service = TitleUseCase(db, agent_llm_facade=self.llm_gateway)

        self.config_service = get_execution_config_service()
        self._memory_indexing = memory_indexing
        self._init_memory_store()

        self._background_tasks: set[asyncio.Task[object]] = set()
        self._event_queues: dict[str, asyncio.Queue[AgentEvent | None]] = {}

    def _init_memory_store(self) -> None:
        """初始化记忆存储"""
        try:
            self.memory_store = LongTermMemoryStore(memory_indexing=self._memory_indexing)
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
        """处理对话请求"""
        await self._ensure_memory_store_initialized()

        mode = (creative_mode or "chat").strip().lower()
        if mode not in ("chat", "image_gen"):
            yield AgentEvent.error(error=f"不支持的创作模式: {creative_mode}", session_id=session_id)
            return

        ref_urls = self._normalize_reference_image_urls(reference_image_urls or [])

        session, session_id, is_new_session = await self._get_or_create_session(
            session_id, user_id, agent_id
        )

        user_metadata = self._build_user_message_metadata(mode, ref_urls)

        if is_new_session:
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
            yield AgentEvent.session_created(session_id)

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
            await self._handle_title_generation(session, session_id, message, user_id)

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

            try:
                engine, session_recreated_event, picked_chat_model_for_persist = (
                    await self._prepare_agent_engine(
                        agent_id, session_id, user_id, session, model_ref
                    )
                )
            except ValidationError as e:
                yield AgentEvent.error(error=e.message, session_id=session_id)
                return

            await self._persist_picked_chat_model_ref(session_id, picked_chat_model_for_persist)

            if session_recreated_event:
                yield session_recreated_event

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
            self._event_queues.pop(session_id, None)
            pending_bg = [t for t in self._background_tasks if not t.done()]
            for task in pending_bg:
                task.cancel()
            if pending_bg:
                await asyncio.gather(*pending_bg, return_exceptions=True)
            self._background_tasks.clear()

    async def resume(
        self,
        session_id: str,
        checkpoint_id: str,
        action: str,
        modified_args: dict | None,
        user_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """恢复中断的执行（Human-in-the-Loop）。"""
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
            task = asyncio.create_task(
                self._generate_title_background(session_id, message, user_id)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _generate_title_background(self, session_id: str, message: str, user_id: str) -> None:
        """后台任务：生成标题（使用独立的数据库会话）"""
        try:
            from domains.session.application.title_use_case import TitleUseCase

            async with get_session_context() as db:
                title_service = TitleUseCase(db, agent_llm_facade=self.llm_gateway)
                success = await title_service.generate_and_update(
                    session_id=session_id,
                    strategy="first_message",
                    message=message,
                    user_id=user_id,
                )

                if success:
                    session_use_case = self._session_use_case_factory(db)
                    session = await session_use_case.get_session(session_id)
                    if session and session.title:
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
            if await self._model_resolution.is_valid_text_personal_model_ref(sid):
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
        if await self._model_resolution.is_valid_text_personal_model_ref(uid):
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
