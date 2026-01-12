"""
Chat Service - 对话服务

实现 Agent 执行引擎的封装
"""

from collections.abc import AsyncGenerator
from typing import Any

from core.engine.agent import AgentEngine
from core.engine.checkpointer import Checkpointer
from core.llm.gateway import LLMGateway
from core.types import AgentConfig, AgentEvent, EventType
from schemas.message import ChatEvent
from services.session import SessionService
from tools.registry import ToolRegistry
from utils.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """对话服务"""

    def __init__(self) -> None:
        self.llm_gateway = LLMGateway()
        self.tool_registry = ToolRegistry()
        self.checkpointer = Checkpointer()
        self.session_service = SessionService()

    async def chat(
        self,
        session_id: str | None,
        message: str,
        agent_id: str | None,
        user_id: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """
        处理对话请求

        Args:
            session_id: 会话 ID (可选，不提供则创建新会话)
            message: 用户消息
            agent_id: Agent ID (可选)
            user_id: 用户 ID

        Yields:
            ChatEvent: 聊天事件流
        """
        # 创建或获取会话
        if not session_id:
            session = await self.session_service.create(
                user_id=user_id,
                agent_id=agent_id,
            )
            session_id = str(session.id)

        # 保存用户消息
        await self.session_service.add_message(
            session_id=session_id,
            role="user",
            content=message,
        )

        # 创建 Agent 配置
        config = await self._get_agent_config(agent_id)

        # 创建执行引擎
        engine = AgentEngine(
            config=config,
            llm_gateway=self.llm_gateway,
            tool_registry=self.tool_registry,
            checkpointer=self.checkpointer,
        )

        # 执行 Agent
        final_content = ""
        try:
            async for event in engine.run(
                session_id=session_id,
                user_message=message,
            ):
                # 转换为 ChatEvent
                chat_event = self._convert_event(event)
                yield chat_event

                # 收集最终内容
                if event.type == EventType.TEXT:
                    final_content = event.data.get("content", "")
                elif event.type == EventType.DONE and not final_content:
                    final_msg = event.data.get("final_message")
                    if final_msg and final_msg.get("content"):
                        final_content = final_msg["content"]

            # 保存助手消息
            if final_content:
                await self.session_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_content,
                )

        except Exception as e:
            logger.error(f"Chat error: {e}")
            yield ChatEvent(
                type="error",
                data={"error": str(e)},
            )

    async def resume(
        self,
        session_id: str,  # noqa: ARG002 - 保留用于日志和审计
        checkpoint_id: str,
        action: str,
        modified_args: dict[str, Any] | None,
        user_id: str,  # noqa: ARG002 - 保留用于权限验证扩展
    ) -> AsyncGenerator[ChatEvent, None]:
        """
        从中断点恢复执行

        Args:
            session_id: 会话 ID
            checkpoint_id: 检查点 ID
            action: 用户操作 (approve/reject/modify)
            modified_args: 修改后的参数
            user_id: 用户 ID

        Yields:
            ChatEvent: 聊天事件流
        """
        # 获取检查点信息
        checkpoint = await self.checkpointer.get(checkpoint_id)
        if not checkpoint:
            yield ChatEvent(
                type="error",
                data={"error": "Checkpoint not found"},
            )
            return

        # 获取 Agent 配置
        config = await self._get_agent_config(None)

        # 创建执行引擎
        engine = AgentEngine(
            config=config,
            llm_gateway=self.llm_gateway,
            tool_registry=self.tool_registry,
            checkpointer=self.checkpointer,
        )

        # 恢复执行
        async for event in engine.resume(
            checkpoint_id=checkpoint_id,
            action=action,
            modified_args=modified_args,
        ):
            yield self._convert_event(event)

    async def _get_agent_config(self, agent_id: str | None) -> AgentConfig:
        """获取 Agent 配置"""
        # TODO: 实现从数据库加载 Agent 配置
        _ = agent_id  # 抑制未使用警告，待实现数据库加载

        # 返回默认配置
        return AgentConfig(
            name="Default Agent",
            model="claude-3-5-sonnet-20241022",
            max_iterations=20,
            temperature=0.7,
            max_tokens=4096,
            tools=["read_file", "write_file", "list_dir", "run_shell", "search_code"],
            checkpoint_enabled=True,
            checkpoint_interval=5,
            hitl_enabled=True,
            hitl_operations=["run_shell", "write_file"],
        )

    def _convert_event(self, event: AgentEvent) -> ChatEvent:
        """转换 AgentEvent 为 ChatEvent"""
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

        return ChatEvent(
            type=type_mapping.get(event.type, str(event.type)),
            data=event.data,
            timestamp=event.timestamp,
        )
